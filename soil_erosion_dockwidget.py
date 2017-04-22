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

from PyQt4.QtCore import QSettings, pyqtSignal, QFileInfo, QVariant, QThread
from PyQt4.QtGui import QFileDialog, QComboBox, QProgressBar
from qgis.core import QgsProviderRegistry, QgsVectorLayer, QgsField
from qgis.utils import iface
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel
from qgis.analysis import QgsOverlayAnalyzer

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
        data = []
        dmt_layer = self.raster_box.currentLayer()
        dmt_path = dmt_layer.dataProvider().dataSourceUri()
        data.append(dmt_path)
        dmt_name = os.path.splitext(os.path.basename(dmt_path))[0]

        bpej_layer = self.shp_box_bpej.currentLayer()
        bpej_path = bpej_layer.dataProvider().dataSourceUri()
        data.append(bpej_path [:bpej_path.rfind('|')])
        bpej_name = os.path.splitext(os.path.basename(bpej_path))[0]

        lpis_layer = self.shp_box_lpis.currentLayer()
        lpis_path = lpis_layer.dataProvider().dataSourceUri()
        data.append(lpis_path [:lpis_path.rfind('|')])
        lpis_name = os.path.splitext(os.path.basename(lpis_path))[0]

        er = ErosionUSLE(dmt_name, bpej_name, lpis_name)
        er.computeProgress.connect(self.progressBar)
        # TODO: show progress (import, run)
        er.import_files(data)
        er.run()
        # er.export()
        # pridat vysledek do mapove okna

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
        self.iface.messageBar().pushWidget(self.progressMessageBar, iface.messageBar().INFO)

        self.cancelButton.clicked.connect(self.onCancelButton)

