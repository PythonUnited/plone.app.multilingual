# -*- encoding: utf-8 -*-

from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.content import Container
from zope.interface import alsoProvides
from zope.interface import implements
from zope.component import adapts
from Products.CMFCore.utils import getToolByName

from plone.folder.interfaces import IExplicitOrdering
from zope.component.hooks import getSite

from plone.app.multilingual.interfaces import ILanguageRootFolder
from plone.app.layout.navigation.interfaces import INavigationRoot

from plone.folder.ordered import CMFOrderedBTreeFolderBase
from Acquisition import aq_base, aq_inner, aq_parent
from Products.Archetypes.interfaces import IBaseObject
from BTrees.OIBTree import union
from Products.ZCatalog.Lazy import LazyMap
from Products.CMFPlone.interfaces import IPloneSiteRoot
from plone.folder.default import DefaultOrdering

from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory

from plone.i18n.locales.languages import _languagelist
from plone.i18n.locales.languages import _combinedlanguagelist

_marker = object()


class LanguageRootFolder(Container):
    """ Language root folder type that holds the shared and is navigation root
    """

    implements(ILanguageRootFolder, INavigationRoot, IPloneSiteRoot)

    def has_key(self, id):
        """Indicates whether the folder has an item by ID.
        """
        if CMFOrderedBTreeFolderBase.has_key(self, id):
            return True
        return id in getSite()

    hasObject = has_key

    def __contains__(self, name):
        return self.has_key(name)

    def __getattr__(self, name):
        try:
            return Container.__getattr__(self, name)
        except AttributeError:
            # Check if it's on shared folder
            # Search for the content on the shared folder
            portal = getSite()
            if portal is not None and name in portal:
                # XXX Check that is content

                new_object = aq_base(getattr(portal, name)).__of__(self)
                new_object._v_is_shared_content = True
                return new_object
            else:
                raise

    def _checkId(self, id, allow_dup=0):
        """ check only locally """
        if not allow_dup and id in CMFOrderedBTreeFolderBase.objectIds(self, None, False):
            raise BadRequestException('The id "%s" is invalid--'
                                      'it is already in use.' % id)

    def _delOb(self, id):
        """ Remove the named object from the folder or parent. """
        obj = CMFOrderedBTreeFolderBase._getOb(self, id, default)
        if obj:
            super(LanguageRootFolder, self)._delOb(id)
        else:
            aliased = getSite()
            if aliased and id in aliased:
                aliased._delOb(id)
            else:
                raise
        self.getOrdering().notifyRemoved(id)   # notify the ordering adapter

    def _getOb(self, id, default=_marker):

        obj = CMFOrderedBTreeFolderBase._getOb(self, id, default)
        if obj:
            return obj
        else:
            aliased = getSite()
            if aliased:
                obj = aliased._getOb(id, default)
                if obj is default:
                    if default is _marker:
                        raise
                    return default
                new_object = aq_base(obj).__of__(self)
                new_object._v_is_shared_content = True
                return new_object

    def objectIds(self, spec=None, ordered=True):
        aliased = getSite()
        # XXX : need to find better aproach
        try:
            if aliased is not None:
                to_remove = []
                aliased_objectIds = aliased.objectIds(spec)
                for id in aliased_objectIds:
                    if id in _languagelist or id in _combinedlanguagelist:
                        to_remove.append(id)
                        
                for id in to_remove:
                    aliased_objectIds.remove(id)
            else:
                aliased_objectIds = ()

        except AttributeError:
            aliased_objectIds = ()

        own_elements = CMFOrderedBTreeFolderBase.objectIds(self, spec, False)

        if len(own_elements) == 0 and aliased_objectIds:
            return aliased_objectIds
        else:
            try:
                return own_elements + aliased_objectIds
            except TypeError:
                return own_elements


    def __getitem__(self, key):
        aliased = getSite()
        try:
            obj = aliased.__getitem__(key)
            new_object = aq_base(obj).__of__(self)
            new_object._v_is_shared_content = True
            return new_object
        except KeyError:
            return CMFOrderedBTreeFolderBase.__getitem__(self, key)


class LRFOrdering(DefaultOrdering):
    """ This implementation checks if there is any object that is not on the list
    in case its a shared object so you can move. """

    implements(IExplicitOrdering)
    adapts(ILanguageRootFolder)


    def idsInOrder(self):
        """ see interfaces.py """
        to_renew = [x for x in self.context.objectIds() if x not in self._pos().keys()]
        to_remove = [x for x in self._pos().keys() if x not in self.context.objectIds()]
        for id in to_renew:
            self.notifyAdded(id)
        for id in to_remove:
            self.notifyRemoved(id)
        return list(self._order())

    def getObjectPosition(self, id):
        """ see interfaces.py """
        pos = self._pos()
        if id in pos:
            return pos[id]
        else:
            aliased = getSite()
            if id in aliased.objectIds():
                self.notifyAdded(id)
                pos = self._pos()
                return pos[id]
            else:
                raise ValueError('No object with id "%s" exists.' % id)
