# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SoilErosionDockWidget
                                 A QGIS plugin
 This plugin computes soil loss on arable land.
                             -------------------
        begin                : 2017-03-08
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Radek Novotny
        email                : radeknovotny94@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import tempfile
import shutil

from PyQt4.QtCore import QSettings, pyqtSignal, QFileInfo, QVariant, QThread, Qt
from PyQt4.QtGui import QFileDialog, QComboBox, QProgressBar, QToolButton, QMessageBox, QColor
from qgis.core import QgsProviderRegistry, QgsVectorLayer, QgsRasterLayer, QgsField, QgsMapLayerRegistry, QgsRasterBandStats, QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer
from qgis.utils import iface
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel
from qgis.analysis import QgsZonalStatistics
# from qgis.analysis import QgsOverlayAnalyzer

from PyQt4 import QtGui, uic

from pyerosion.read_csv import ReadCSV
from pyerosion.erosionusle import ErosionUSLE

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'soil_erosion_dockwidget_base.ui'))


class SoilErosionDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(SoilErosionDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.settings = QSettings("CTU", "Erosion_plugin")

        self.iface = iface

        # Define first computation, no results in map window
        self._first_computation = True

        # Read code tables
        self._factors = {}
        self._readFactorCodes()

        # Fill C combobox
        self.combobox_c.clear()
        list = self._factors['C'].list()
        self.combobox_c.addItems(list)

        # Set filters for QgsMapLayerComboBoxes
        self.shp_box_euc.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.load_shp_euc.clicked.connect(self.onLoadShapefile)
        
        self.raster_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.load_raster.clicked.connect(self.onLoadRaster)

        self.shp_box_bpej.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.load_shp_bpej.clicked.connect(self.onLoadShapefile)

        self.shp_box_lpis.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.load_lpis.clicked.connect(self.onLoadShapefile)

        # Set functions for buttons
        self.compute_k_button.clicked.connect(self.onAddKFactor)
        self.compute_c_button.clicked.connect(self.onAddCFactor)

        self.set_button.clicked.connect(self.onCompute)
                
    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def onLoadRaster(self):
        """Open 'Add raster layer dialog'."""
        sender = '{}-lastUserFilePath'.format(self.sender().objectName())
        lastUsedFilePath = self.settings.value(sender, '')

        fileName = QFileDialog.getOpenFileName(self,self.tr(u'Open Raster'), 
                                               self.tr(u'{}').format(lastUsedFilePath),
                                               QgsProviderRegistry.instance().fileRasterFilters())
        if fileName:
            self.iface.addRasterLayer(fileName, QFileInfo(fileName).baseName())
            self.settings.setValue(sender, os.path.dirname(fileName))

    def onLoadShapefile(self):
        """Open 'Add shapefile layer dialog'."""
        sender = '{}-lastUserFilePath'.format(self.sender().objectName())
        lastUsedFilePath = self.settings.value(sender, '')
        
        fileName = QFileDialog.getOpenFileName(self,self.tr(u'Open Shapefile'),
                                               self.tr(u'{}').format(lastUsedFilePath), 
                                               QgsProviderRegistry.instance().fileVectorFilters())
        if fileName:
            self.iface.addVectorLayer(fileName, QFileInfo(fileName).baseName(), "ogr")
            self.settings.setValue(sender, os.path.dirname(fileName))

    def onAddKFactor(self):
        bpej_layer = self.shp_box_bpej.currentLayer()
        if bpej_layer is None:
            # TODO: pushMessage()
            return
        else:
            bpej_layer.startEditing()
            self._addColumn(bpej_layer, 'K')
            bpej_layer.commitChanges()

        bpej_layer.startEditing()
        idx = bpej_layer.fieldNameIndex('BPEJ')
        for feature in bpej_layer.getFeatures():
            bpej = feature.attributes()[idx]
            fid = feature.id()
            if bpej == '99':
                k_value = 0
            else:
                k_value = self._factors['K'].value(bpej[2] + bpej[3])
            self.setFieldValue(bpej_layer, 'K', k_value, fid)
        bpej_layer.commitChanges()
        
    def onAddCFactor(self):
        lpis_layer = self.shp_box_lpis.currentLayer()
        if lpis_layer is None:
            # TODO: pushMessage()
            return
        else:
            lpis_layer.startEditing()
            self._addColumn(lpis_layer, 'C')
            lpis_layer.commitChanges()

        lpis_layer.startEditing()
        combobox_value = self.combobox_c.currentText()
        idx = lpis_layer.fieldNameIndex('KULTURAKOD')
        for feature in lpis_layer.getFeatures():
            lpis = feature.attributes()[idx]
            fid = feature.id()
            if lpis == 'T':
                c_value = 0.005
            elif lpis == 'S':
                c_value = 0.45
            elif lpis == 'L':
                c_value = 0
            elif lpis == 'V':
                c_value = 0
            elif lpis == 'C':
                c_value = 0.8
            elif lpis == 'R':
                c_value = self._factors['C'].value(combobox_value)
            self.setFieldValue(lpis_layer, 'C', c_value, fid)
        lpis_layer.commitChanges()
        
    def setFieldValue(self, euc_layer, field_name, value, fid=None):
        index = euc_layer.dataProvider().fieldNameIndex(field_name)
        
        if fid is None:
            for feature in euc_layer.getFeatures():
                fid = feature.id()
                euc_layer.changeAttributeValue(fid, index, value)
        else:
            euc_layer.changeAttributeValue(fid, index, value)
        
    def _readFactorCodes(self):
        for fact in ('K','C'):
            filename = os.path.join(os.path.dirname(__file__), 'code_tables', fact + '_factor.csv')
            self._factors[fact] = ReadCSV(filename)

    def _addColumn(self, layer, name):
        for field in layer.pendingFields():
            if field.name() == name:
                return

        # column does not exists
        # TODO
        # caps & QgsVectorDataProvider.AddAttributes):
        layer.dataProvider().addAttributes(
            [QgsField(name, QVariant.Double)]
        )
        
    # def onIntersectLayers(self):
    #     euc_layer = self.shp_box_euc.currentLayer()
    #     bpej_layer = self.shp_box_bpej.currentLayer()
    #     analyzer = QgsOverlayAnalyzer()
    #     analyzer.intersection(euc_layer, bpej_layer, os.path.join(os.path.dirname(__file__), 'intersect.shp'), False, None)

    def onCompute(self):
        if hasattr(self, "computeThread"):
            return
        # remove results from map window, if it is not first computation
        if self._first_computation == False:
            QgsMapLayerRegistry.instance().removeMapLayer(self._se_layer.id())

        # find input layers
        euc_layer = self.shp_box_euc.currentLayer()
        dmt_layer = self.raster_box.currentLayer()
        bpej_layer = self.shp_box_bpej.currentLayer()
        lpis_layer = self.shp_box_lpis.currentLayer()

        # check fields
        self._cancel = False
        self.checkField('BPEJ', bpej_layer, 'K')
        if self._cancel == True:
            return

        self.checkField('LPIS', lpis_layer, 'C')
        if self._cancel == True:
            return

        # check crs of input layers
        euc_crs = euc_layer.crs().authid()
        dmt_crs = dmt_layer.crs().authid()
        bpej_crs = bpej_layer.crs().authid()
        lpis_crs = lpis_layer.crs().authid()
        if euc_crs == dmt_crs == bpej_crs == lpis_crs:
            if not int(euc_crs[5:]) >= 100000:
                epsg = int(euc_crs[5:])
            else:
                self.showError(u'It\'s not allow compute in own projection!\n\nSet CRS of'\
                               u' input layers: {}\n\nPlease change CRS of input layers.'.format(euc_crs))
                return
        else:
            self.showError(u'Layers have different projection:\nEUC: {}\nDMT: {}\nBPEJ: {}\nLP'\
                           u'IS: {}'.format(euc_crs, dmt_crs, bpej_crs, lpis_crs))
            return

        # add paths to layers to data
        data = []

        euc_path = euc_layer.dataProvider().dataSourceUri()
        data.append(euc_path[:euc_path.rfind('|')])

        dmt_path = dmt_layer.dataProvider().dataSourceUri()
        data.append(dmt_path)

        bpej_path = bpej_layer.dataProvider().dataSourceUri()
        data.append(bpej_path [:bpej_path.rfind('|')])

        lpis_path = lpis_layer.dataProvider().dataSourceUri()
        data.append(lpis_path [:lpis_path.rfind('|')])

        self.progressBar()
        self.computeThread = ComputeThread(data, epsg)
        self.computeThread.computeFinished.connect(lambda: self.importResults(epsg))
        self.computeThread.computeStat.connect(self.setStatus)
        self.computeThread.computeError.connect(self.showError)
        #self.computeThread.computeProgress.connect(self.progressBar)
        if not self.computeThread.isRunning():
            self.computeThread.start()

    def checkField(self, name_lyr, layer, field_name):
        if layer.fieldNameIndex(field_name) == -1:
            self.showError(u'{} layer must contain field {}'.format(name_lyr, field_name))
            self._cancel = True

    def showError(self, text):
        QMessageBox.critical(self, u'Soil Erosion Plugin', u"{}".format(text))

    def importResults(self, epsg):
        # if self.computeThread.aborted:
        #     return

        # Import results to QGIS
        temp_path = self.computeThread.output_path()
        for file in os.listdir(temp_path):
            if file.endswith(".tif"):
                self._se_layer = iface.addRasterLayer(os.path.join(temp_path, file),
                                                'Soil Erosion')
                crs = self._se_layer.crs()
                crs.createFromId(epsg)
                self._se_layer.setCrs(crs)
                # # Set style be renderer:
                # self.setStyle(self._se_layer)
                # # set style on .gml file:
                # style_name = os.path.join(os.path.dirname(__file__),
                #                           'style', 'colors.gml')
                # self._se_layer.loadNamedStyle(style_name)
                euc = self.shp_box_euc.currentLayer()
                se_source = self._se_layer.source()
                self.zonalStat(euc, se_source)
        self._first_computation = False

        self.computeThread.cleanup()
        del self.computeThread
        # kill progress bar if it is still on (if computation is still on)
        try:
            self.progress.setParent(None)
            self.iface.messageBar().popWidget(self.progressMessageBar)
        except:
            pass

    def progressBar(self):
        """Initializing progress bar.

        :text: message to indicate what operation is currently on
        """
        self.progressMessageBar = iface.messageBar().createMessage(u"Erosion Plugin:", u" Computing...")
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.cancelButton = QtGui.QPushButton()
        self.cancelButton.setText('Cancel')
        self.progressMessageBar.layout().addWidget(self.cancelButton)
        self.progressMessageBar.layout().addWidget(self.progress)

        msgBar = self.iface.messageBar()
        msgBar.pushWidget(self.progressMessageBar, iface.messageBar().INFO)
        msgBar.findChildren(QToolButton)[0].setHidden(True)

        self.cancelButton.clicked.connect(self.onCancelButton)

    def onCancelButton(self):
        """Show message box with question on canceling. Cancel computation."""

        reply = QMessageBox.question(self, u'Soil Erosion Plugin',
                                     u"Cancel computation?{ls}".format(
                                         ls=2 * os.linesep),
                                     QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                                     QtGui.QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.computeThread.terminate()
            self.computeThread.cleanup()
            del self.computeThread

            # kill progress bar if it is still on (if computation is still on)
            try:
                self.progress.setParent(None)
                self.iface.messageBar().popWidget(self.progressMessageBar)
            except:
                pass

    def setStatus(self, num, text):
        """Update progress status.

        :num: progress percent
        """
        self.progressMessageBar.setText(text)
        self.progress.setFormat('{}%'.format(num))
        self.progress.setValue(num)

    def setStyle(self, layer):
        provider = layer.dataProvider()
        extent = layer.extent()

        stats = provider.bandStatistics(1, QgsRasterBandStats.All, extent, 0)
        if stats.minimumValue < 0:
            min = 0
        else:
            min = stats.minimumValue

        max = stats.maximumValue
        range = max - min
        add = range // 2
        interval = min + add

        colDic = {'red': '#ff0000', 'yellow': '#ffff00', 'blue': '#0000ff'}

        valueList = [min, interval, max]

        lst = [QgsColorRampShader.ColorRampItem(valueList[0], QColor(colDic['red'])),
               QgsColorRampShader.ColorRampItem(valueList[1], QColor(colDic['yellow'])),
               QgsColorRampShader.ColorRampItem(valueList[2], QColor(colDic['blue']))]

        myRasterShader = QgsRasterShader()
        myColorRamp = QgsColorRampShader()

        myColorRamp.setColorRampItemList(lst)
        myColorRamp.setColorRampType(QgsColorRampShader.INTERPOLATED)
        # TODO: add classificationMode=Continuos
        # myColorRamp.setClassificationMode(QgsColorRampShader.ClassificationMode(1))
        # AttributeError: type object 'QgsColorRampShader' has no attribute 'setClassificationMode'
        myRasterShader.setRasterShaderFunction(myColorRamp)

        myPseudoRenderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(),
                                                            layer.type(),
                                                            myRasterShader)

        layer.setRenderer(myPseudoRenderer)

        layer.triggerRepaint()

    def zonalStat(self, vlayer, rlayer_source):
        prefix = 'Erosion_'
        zonalstats = QgsZonalStatistics(vlayer, rlayer_source, prefix, stats=QgsZonalStatistics.Statistic(4))
        zonalstats.calculateStatistics(None)

class ComputeThread(QThread):
    # set signals:
    computeStat = pyqtSignal(int, str)
    computeFinished = pyqtSignal()
    computeError = pyqtSignal(str)
    
    def __init__(self, data, epsg):
        QThread.__init__(self)
        self.data = data
        self.epsg = epsg
        self.er = None

    def cleanup(self):
        # remove directory with temporary files
        if self.er:
            shutil.rmtree(self.er.location_path())

    def run(self):
        self.er = ErosionUSLE(self.data, self.epsg, computeStat=self.computeStat, computeError=self.computeError)
        try:
            self.er.import_data(self.data)
        except:
            self.computeError.emit(u'Error during exporting layers to Grass for computation.')
        self.er.run()
        # Export results to temporary directory
        self.computeStat.emit(99, u'Export data to map window...')
        try:
            self.temp_path = tempfile.mkdtemp()
            self.er.export_data(self.temp_path)
        except:
            self.computeError.emit(u'Error during importing results to map window.')
        self.computeFinished.emit()

    def output_path(self):
        return self.temp_path
