# -*- coding: utf-8 -*-
# This file is part of Argos.
#
# Argos is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Argos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Argos. If not, see <http://www.gnu.org/licenses/>.

""" Repository tree.
"""
from __future__ import print_function

import logging
from libargos.qt import QtGui, QtCore, QtSlot, Qt
from libargos.config.groupcti import MainGroupCti
from libargos.config.boolcti import BoolCti
from libargos.repo.registry import globalRtiRegistry
from libargos.repo.repotreemodel import RepoTreeModel
from libargos.widgets.argostreeview import ArgosTreeView
from libargos.widgets.constants import (LEFT_DOCK_WIDTH, COL_NODE_NAME_WIDTH,
                                        COL_SHAPE_WIDTH, COL_ELEM_TYPE_WIDTH)

logger = logging.getLogger(__name__)

# Qt classes have many ancestors
#pylint: disable=R0901

class RepoTreeView(ArgosTreeView):
    """ Tree widget for browsing the data repository.

        Currently it supports only selecting one item. That is, the current item is always the
        selected item (see notes in ArgosTreeView documentation for details).

    """
    def __init__(self, repoTreeModel, collector, parent=None):
        """ Constructor.

            Maintains a reference to a collector. The repo tree view updates the collector when
            the currentIndex changes.
        """
        super(RepoTreeView, self).__init__(treeModel=repoTreeModel, parent=parent)

        self._collector = collector
        self._config = self._createConfig()

        treeHeader = self.header()
        treeHeader.resizeSection(RepoTreeModel.COL_NODE_NAME, COL_NODE_NAME_WIDTH)
        treeHeader.resizeSection(RepoTreeModel.COL_SHAPE, COL_SHAPE_WIDTH)
        treeHeader.resizeSection(RepoTreeModel.COL_ELEM_TYPE, COL_ELEM_TYPE_WIDTH)
        treeHeader.setStretchLastSection(True)

        headerNames = self.model().horizontalHeaders
        enabled = dict((name, True) for name in headerNames)
        enabled[headerNames[RepoTreeModel.COL_NODE_NAME]] = False # Cannot be unchecked
        checked = dict((name, False) for name in headerNames)
        checked[headerNames[RepoTreeModel.COL_NODE_NAME]] = True
        checked[headerNames[RepoTreeModel.COL_SHAPE]] = False
        checked[headerNames[RepoTreeModel.COL_ELEM_TYPE]] = False
        self.addHeaderContextMenu(checked=checked, enabled=enabled, checkable={})

        self.setContextMenuPolicy(Qt.DefaultContextMenu) # will call contextMenuEvent
        self.setUniformRowHeights(True)

        # Add actions
        self.topLevelItemActionGroup = QtGui.QActionGroup(self) # TODO: not used anymore?
        self.topLevelItemActionGroup.setExclusive(False)
        self.currentItemActionGroup = QtGui.QActionGroup(self)
        self.currentItemActionGroup.setExclusive(False)

        removeFileAction = QtGui.QAction("Remove from Tree", self.currentItemActionGroup,
                                         shortcut=QtGui.QKeySequence.Delete,
                                         triggered=self.removeCurrentItem)
        self.addAction(removeFileAction)

        reloadFileAction = QtGui.QAction("Reload File", self.currentItemActionGroup,
                                         shortcut=QtGui.QKeySequence.Refresh,   #"Ctrl+R",
                                         triggered=self.reloadFileOfCurrentItem)
        self.addAction(reloadFileAction)

        self.openItemAction = QtGui.QAction("Open Item", self,
                                       #shortcut="Ctrl+Shift+C",
                                       triggered=self.openCurrentItem)
        self.addAction(self.openItemAction)

        self.closeItemAction = QtGui.QAction("Close Item", self,
                                        #shortcut="Ctrl+C", # Ctrl+C already taken for Copy
                                        triggered=self.closeCurrentItem)
        self.addAction(self.closeItemAction)

        # Connect signals
        selectionModel = self.selectionModel() # need to store to prevent crash in PySide
        selectionModel.currentChanged.connect(self.updateCurrentItemActions)
        selectionModel.currentChanged.connect(self.updateCollector)


    def contextMenuEvent(self, event):
        """ Creates and executes the context menu for the tree view
        """
        menu = QtGui.QMenu(self)

        for action in self.actions():
            menu.addAction(action)

        openAsMenu = self.createOpenAsMenu(parent=menu)
        menu.insertMenu(self.closeItemAction, openAsMenu)

        menu.exec_(event.globalPos())



    def createOpenAsMenu(self, parent=None):
        """ Creates the submenu for the Open As choice
        """
        openAsMenu = QtGui.QMenu(parent=parent)
        openAsMenu.setTitle("Open Item As")

        registry = globalRtiRegistry()
        for rtiRegItem in registry.items:
            #rtiRegItem.tryImportClass()
            def createTrigger():
                """Function to create a closure with the regItem"""
                _rtiRegItem = rtiRegItem # keep reference in closure
                return lambda: self.reloadFileOfCurrentItem(_rtiRegItem)

            action = QtGui.QAction("{}".format(rtiRegItem.name), self,
                enabled=bool(rtiRegItem.successfullyImported is not False),
                triggered=createTrigger())
            openAsMenu.addAction(action)

        return openAsMenu



    def finalize(self):
        """ Disconnects signals and frees resources
        """
        selectionModel = self.selectionModel() # need to store to prevent crash in PySide
        selectionModel.currentChanged.disconnect(self.updateCollector)
        selectionModel.currentChanged.disconnect(self.updateCurrentItemActions)


    @property
    def config(self):
        """ The root config tree item for this widget
        """
        return self._config


    def _createConfig(self):
        """ Creates a config tree item (CTI) hierarchy containing default children.
        """
        rootItem = MainGroupCti('data repository')
        rootItem.insertChild(BoolCti('my checkbox', False)) # Does nothing yet
        return rootItem


    @property
    def collector(self): # TODO: move to selector class in the future
        """ The collector that this selector view will update. Read only property.
        """
        return self._collector

    def sizeHint(self):
        """ The recommended size for the widget."""
        return QtCore.QSize(LEFT_DOCK_WIDTH, 450)


    @QtSlot(QtCore.QModelIndex, QtCore.QModelIndex)
    def updateCurrentItemActions(self, currentIndex, _previousIndex):
        """ Enables/disables actions when a new item is the current item in the tree view.
        """
        logger.debug("updateCurrentItemActions... ")

        # When the model is empty the current index may be invalid.
        hasCurrent = currentIndex.isValid()
        self.currentItemActionGroup.setEnabled(hasCurrent)

        isTopLevel = hasCurrent and self.model().isTopLevelIndex(currentIndex) #
        self.topLevelItemActionGroup.setEnabled(isTopLevel)

        currentItem = self.model().getItem(currentIndex)
        self.openItemAction.setEnabled(currentItem.hasChildren() and not currentItem.isOpen)
        self.closeItemAction.setEnabled(currentItem.hasChildren() and currentItem.isOpen)



    @QtSlot()
    def openCurrentItem(self):
        """ Opens the current item in the repository.
        """
        logger.debug("openCurrentItem")
        _currentIten, currentIndex = self.getCurrentItem()
        if not currentIndex.isValid():
            return

        # Expanding the node will visit the children and thus show the 'open' icons
        self.expand(currentIndex)


    @QtSlot()
    def closeCurrentItem(self):
        """ Closes the current item in the repository.
            All its children will be unfetched and closed.
        """
        logger.debug("closeCurrentItem")
        currentItem, currentIndex = self.getCurrentItem()
        if not currentIndex.isValid():
            return

        # First we remove all the children, this will close them as well.
        self.model().removeAllChildrenAtIndex(currentIndex)
        currentItem.close()
        self.dataChanged(currentIndex, currentIndex)
        self.collapse(currentIndex) # otherwise the children will be fetched immediately
                                    # Note that this will happen anyway if the item is e in
                                    # in another view (TODO: what to do about this?)

    # @QtSlot()
    # def __not_used__removeCurrentFile(self):
    #     """ Finds the root of of the current item, which represents a file,
    #         and removes it from the list.
    #     """
    #     logger.debug("removeCurrentFile")
    #     currentIndex = self.getRowCurrentIndex()
    #     if not currentIndex.isValid():
    #         return
    #
    #     topLevelIndex = self.model().findTopLevelItemIndex(currentIndex)
    #     self.model().deleteItemAtIndex(topLevelIndex) # this will close the items resources.


    @QtSlot()
    def removeCurrentItem(self):
        """ Removes the current item from the repository tree.
        """
        logger.debug("removeCurrentFile")
        currentIndex = self.getRowCurrentIndex()
        if not currentIndex.isValid():
            return

        self.model().deleteItemAtIndex(currentIndex) # this will close the items resources.


    @QtSlot()
    def reloadFileOfCurrentItem(self, rtiRegItem=None):
        """ Finds the repo tree item that holds the file of the current item and reloads it.
            Reloading is done by removing the repo tree item and inserting a new one.

            The new item will have by of type rtiRegItem.cls. If rtiRegItem is None (the default),
            the new rtiClass will be the same as the old one.
            The rtiRegItem.cls will be imported. If this fails the old class will be used, and a
            warning will be logged.
        """
        logger.debug("reloadFileOfCurrentItem, rtiClass={}".format(rtiRegItem))

        currentIndex = self.getRowCurrentIndex()
        if not currentIndex.isValid():
            return

        fileRtiIndex = self.model().findFileRtiIndex(currentIndex)
        isExpanded = self.isExpanded(fileRtiIndex)

        if rtiRegItem is None:
            rtiClass = None
        else:
            rtiRegItem.tryImportClass()
            rtiClass = rtiRegItem.cls

        newRtiIndex = self.model().reloadFileAtIndex(fileRtiIndex, rtiClass=rtiClass)
        self.setExpanded(newRtiIndex, isExpanded)
        self.setCurrentIndex(newRtiIndex)
        return newRtiIndex


    @QtSlot(QtCore.QModelIndex, QtCore.QModelIndex)
    def updateCollector(self, currentIndex, _previousIndex):
        """ Updates the collector based on the current selection.

            A selector always operates on one collector. Each selector implementation will update
            the collector in its own way. Therefore the selector maintains a reference to the
            collector.

            TODO: make Selector classes. For now it's in the RepoTreeView.
        """
        # When the model is empty the current index may be invalid.
        hasCurrent = currentIndex.isValid()
        if not hasCurrent:
            return

        rti = self.model().getItem(currentIndex, None)
        assert rti is not None, "sanity check failed. No RTI at current item"

        logger.info("Adding rti to collector: {}".format(rti.nodePath))
        self.collector.setRti(rti)
        #if rti.asArray is not None: # TODO: maybe later, first test how robust it is now
        #    self.collector.setRti(rti)

