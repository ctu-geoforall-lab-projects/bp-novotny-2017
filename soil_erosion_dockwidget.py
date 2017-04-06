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

from PyQt4.QtCore import QSettings, pyqtSignal, QFileInfo, QVariant
from PyQt4.QtGui import QFileDialog
from qgis.core import QgsProviderRegistry, QgsVectorLayer, QgsField
from qgis.utils import iface
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel

from PyQt4 import QtGui, uic

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

        self.settings = QSettings("CTU","Erosion_plugin")

        self.iface = iface

        # Set filters for QgsMapLayerComboBoxes
        self.raster_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.load_raster.clicked.connect(self.onLoadRaster)

        self.shp_box.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.load_shp.clicked.connect(self.onLoadShapefile)

        self.Set_button.clicked.connect(self.onAddKCFactors)

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

    def onAddKCFactors(self):
        """Add K and C factor to attribute table of EUC layer"""
        def _addColumn(layer, name):
            for field in layer.pendingFields():
                if field.name() == name:
                    return

            # column does not exists
            # TODO
            # caps & QgsVectorDataProvider.AddAttributes):
            layer.dataProvider().addAttributes(
                [QgsField(name, QVariant.Double)]
            )
            
        euc_layer=self.shp_box.currentLayer()
        if euc_layer is None:
            # TODO: pushMessage()
            return

        # TODO: check on readonly layers
        euc_layer.startEditing()

        # add attribute columns if not exists
        _addColumn(euc_layer, "K")
        _addColumn(euc_layer, "C")
        euc_layer.commitChanges()

        euc_layer.startEditing()
        fid_k = euc_layer.dataProvider().fieldNameIndex("K")
        fid_c = euc_layer.dataProvider().fieldNameIndex("C")

        k_value=self.k_factor.text()
        c_value=self.c_factor.text()
        
        for feature in euc_layer.getFeatures():
            ID = feature.id()
            euc_layer.changeAttributeValue(ID, fid_k, k_value)
            euc_layer.changeAttributeValue(ID, fid_c, c_value)
    
        euc_layer.commitChanges()






        
