import types

class Code:
    """
    CLASS: Code
    DESCR: Associate integer codes with strings for two-way lookups.
    You give me the string, I'll give you the code.  You give me the
    code, I'll give you the string.
    """
    def __init__( self, desc, codes=0 ):
        """Desc is a list or tuple of descriptions.  Default values
        for codes is [0,1,2,3...N-1]"""
        N = len(desc)
        if isinstance(desc[0], types.StringType):
            if codes ==0:
                codes = range(N)
                if len(codes) != N:
                    raise ValueError, 'desc and codes must be of the same length'
        elif isinstance(desc[0], types.TupleType) and codes == 0:
            tempDescs = []
            tempCodes = []
            for pair in desc:
                tempDescs.append(pair[0])
                tempCodes.append(pair[1])
            codes = tempCodes
            desc = tempDescs
        else:
            if codes == 0:
                raise ValueError, 'desc must be a DictType string->integer'
            else:
                raise ValueError, 'codes and desc must be a list or tuple type'

        self.codes = codes
        self.descs = desc
        self.to_desc = {}
        self.to_code = {}
        for (thisCode, thisDesc) in map(None, codes, desc):
            self.to_desc[ thisCode ] = thisDesc
            self.to_code[ thisDesc ] = thisCode

    def __getitem__(self,i):
        "Return a (code, desc) tuple"
        return (self.codes[i], self.descs[i])

    def get_codes(self):
        """Get a list of the legal codes"""
        return self.codes

    def get_descriptions(self):
        """Get a list of the legal descriptions"""
        return self.descs

    
    def get_code(self, desc):
        """Given a description string 'desc', return the integer code"""
        if self.to_code.has_key(desc):
            return self.to_code[desc]
        else:
            raise ValueError, "Unrecognized description '%s'; "\
                  "legal descriptions are:\n%s" % (desc, self.to_code.keys())

    def get_description(self, code):
        """Given a descritpion string 'desc', return the integer code"""
        if self.to_desc.has_key(code):
            return self.to_desc[code]
        else:
            raise ValueError, "Unrecognized code '%d'; "\
                  "legal descriptions are:\n%s" % (code, self.to_desc.keys())


class CodeBase:
    """
    CLASS: CodeBase
    DESCR: 
    """
    def __init__(self, val):
        """val can either be a code or a description"""
        if isinstance(val, types.IntType):
            self.code = val
        elif isinstance(val, types.StringType):
            self.code = self._codes.get_code(val)
        else:
            raise TypeError, 'Expected an int or a string, got a %s' % val
        self.desc = self._codes.get_description(self.code)
        
    def get_code(self):
        """Get the numeric code"""
        return self.code
    def get_description(self):
        """Get the string description"""
        return self._codes.get_description(self.code)

    
    def __str__(self):
        return self.get_description()
    def __int__(self):
        return self.get_code()


