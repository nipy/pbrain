from Code import Code

#emulate a static registry
class CodeRegistry:
    """
    CLASS: CodeRegistry
    DESCR:
    """ 
    def __init__(self):
        """Init the registry"""
        self.codes = {}
    def add_code(self, id, code):
        """Add a code identified by string to the registry"""
        self.codes[id] = code
    def get_code(self, id):
        return self.codes[id]
    def has_id(self, id):
        return self.codes.has_key(id)
    def get_codes(self):
        return self.codes

_theRegistry = CodeRegistry()

def register_code(id, code):
    """Register the code with the given is string with the registry"""
    #print "Adding %s to the registry" % id
    #print code
    if _theRegistry.has_id(id):
        raise ValueError, 'key %s is already registerd' % id
    _theRegistry.add_code( id, code)

def get_code_from_registry( id ):
    """Get the code from the registry with given id"""
    #print "Trying to get code with key %s" % id
    return _theRegistry.get_code( id )

def get_registry_codes(  ):
    """Get the codes from the registry"""
    return _theRegistry.get_codes( )

def get_registry_keys(  ):
    """Get the keys from the registry codes"""
    return _theRegistry.get_codes().keys()

def get_code_mapping( id ):
    """Get a mapping for codes and descriptions suitable for DTML usage"""
    returnVal = []
    theCodes = _theRegistry.get_code( id )
    codes = theCodes.get_codes()
    descs = theCodes.get_descriptions()
    for (code, desc) in map(None, codes, descs):
        returnVal.append( { 'code' : code, 'description' : desc } )
    return returnVal

def get_description( key, val):
    code = get_code_from_registry( key )
    return code.get_description( val )
