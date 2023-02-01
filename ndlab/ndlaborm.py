"""
Defines the grammar to query the database, and its translation into sql
"""

#%config IPCompleter.greedy = True

import json
import inspect,sys
from operator import truediv

class Sqlbuilder:
    """Parses a string with nuclear data model tokens

     Attributes:
        force_clean (bool):  whether fields and conditions of the query will be "cleaned", e.g. (NUCLIDE.Z -> ( NUCLIDE.Z. 
        When false, the cleaning is done only if the query execution raises an exception

        _classes (Object[]): the classes of this module, used in clean_token() to find their place in a string
    """

# if fields and conditions of the query will be "cleaned", e.g. (NUCLIDE.Z -> ( NUCLIDE.Z
# when false, the cleaning is done only if the query execution raises an exception
    force_clean = False

# the classes of this module, used in clean_token to find where are placed in a string     
    _classes = []

# a string token is evaluated to convert it into an object
# then it will be checked if it is an orm piece
    def interrogate(self,tk):
        try:
            ret = eval(tk)
            #  '241AM' : when the string is between ''
            if ret.__class__.__name__ == "str":
                return tk
            else:
                # this is a string without ''
                return ret
        except:
            return eval("tk")

# checks if an object is a class of this module
    def is_datamodel(self,piece):
        if(piece.__class__.__module__ == __name__ or piece == _Base.ALL):
            return True
        return False 

    # fills the _classes list
    def get_classes(self):
        # lazy
        if(len(self._classes) > 0 ): return self._classes

        for name, obj in inspect.getmembers(sys.modules["ndlaborm"]):
            if inspect.isclass(obj):
                self._classes.append(obj)
                #print('print(description(' + name + '))')
        return self._classes  

    # attributes of a class
    def get_attributes(self,cls):
        attr = []
        dump = dir(type('dump', (object,), {}))

        for item in inspect.getmembers(cls):
            if(item[0] not in dump and item[0] != 'ALL'):
                attr.append(item[0])
        return attr  

    # adds blanks where needed: '(GAMMA.ENERGY=' -->  '( GAMMA.ENERGY ='
    def before_after_class(self,tk, idx, mclass):
        """

        tk the token
        idx the starting of the class name within the token
        mclass the class found in this token
        """
        length = len(mclass.__name__)
        char_before = tk[idx-1: idx]
    
        if(idx > 0 and char_before != '.' and char_before != '_'): #  before: cases like "(GAMMA.ENERGY ..."
            tk =  tk[:idx] + ' ' + tk[idx:]
            length = length + 1

        # after the class there is "." and the fields   
        tks = tk.split(".") 
        # only the last sub-token.
        # for "GAMMA.END_LEVEL.JP" the last token is not a field of the GAMMA class  
        # and will go unchecked now. It will be picked up when clean_tk finds END_LEVEL and passes it back here
        last_tk = tks[len(tks)-1] 
        attribs = self.get_attributes(mclass) 
        idx_max = 0
        len_max = 0
        # check all the possible fields, take the longest name to avoid errors in cases like "J" and "JP"
        for attr in attribs:
            idx = last_tk.find(attr)
            if(idx == -1): continue
            char_after = "" if len(last_tk) == len(attr) else last_tk[idx + len(attr): idx+ len(attr)+1]
            
            # this is a bit ad hoc, it is to deal with :
            # 1 - NUCLIDE.NUC_ID , where also N is a field of nuclide
            # 2 - LEVEL.NUC.NUC_ID where NUC is a class and needs to be separated from NUC_ID
            if(char_after == "_" or  ( attr != last_tk and last_tk.startswith('NUC_ID') and  attr != 'NUC_ID'  )): continue

            mlen = len(attr)
            len_max =  mlen if mlen > len_max else len_max
            idx_max = idx if mlen > len_max else idx_max
        
        if(len_max > 0 and len(last_tk) > len_max):
            last_tk =   last_tk[:idx_max + len_max]  + ' ' + last_tk[idx_max + len_max:]
        tks[len(tks)-1] = last_tk
        
        return ".".join(tks)
                
  
    # take one token (string with no blanks), look for classes and process the token
    def clean_tk(self,tk):
        classes = self.get_classes()
        for mclass in classes:
            idx = tk.find(mclass.__name__) #the token contains a class name
            if(idx > -1):      
                tk = self.before_after_class(tk,idx, mclass) # place blanks if needed
        return tk

    def clean_query(self,str):
        tks_a = str.split()
        # put blanks where needed: 'GAMMA.ENERGY=' -->  'GAMMA.ENERGY ='
        clean_string = ''
        for tk_a in tks_a:
            clean_string += ' ' + self.clean_tk(tk_a)
        return clean_string
        #tks_a = clean_string.split()

    def is_constant(self, const_name):
        for name, obj in inspect.getmembers(sys.modules["ndlaborm"]):
             if(name == str(const_name)) : 
                return [True, obj]
        return [False,const_name]


    #string should have datamodel tokens separated by ' '
    def parse(self,string):
    # string should be like '( Gamma.start_level.energy - Gamma.end_level.energy ) = 100'

        fields = []
        tables = []
        fks = []
        tables_nofks = [] # "true" tables, not from a fk addition
        # table.* will be prefixed with DISTINCT
        if(string.endswith(".*")):
            string = string.replace(".*",".ALL")

        tks_a = string.split() # datamodel must have blank spaces. Use clean_query to pre-process
        for tk_a in tks_a:
            try:
                # check what kind of staff is tk_a
                piece = (self.interrogate(tk_a))
              
                # if it is one of the constants, like DELAY_N
                dummy = self.is_constant(str(tk_a)) 
                if(dummy[0]):
                    if(dummy[1].__class__.__name__ == "str"):
                        # string, add quotes
                        dummy[1] = "'" + dummy[1] + "'" 

                    fields.append(str(dummy[1])) # str in case is an integer

                elif not self.is_datamodel(piece):
                      # it is not part of the datamodel: leave as it is
                    fields.append(str(piece))
                  
                else:  # it is data model
                    tks_b = tk_a.split(".")
                    tot = len(tks_b)
                    #print("tot", tot)
                    # from GAMMA.START_LEVEL.ENERGY  build the array [GAMMA.START_LEVEL.ENERGY, GAMMA.START_LEVEL, GAMMA]
                    tks_c = []
                    for i in range(0, tot):
                        dm = ".".join(tks_b[0:tot -i])
                        tks_c.append(eval(dm))
                    # process the pieces, so far only 3 levels are dealt with. Remeber: the pieces go backward
                    for i in range(0, tot):
                        tk = tks_c[i]
                        if(i == 0): # this is a column
                            if(tk == _Base.ALL):
                                column = "*"
                            else:
                                column = (tk.data["column"])
                        if(i == 1 ): # this can be a table, or a foreign key
                            if 'table' not in tk.data: # this is fk
                                tblnm = self.table_name(tk) # tk.data["fk"]["table"] + (( " as " + tk.data["fk"]["alias"]) if "alias" in tk.data["fk"].keys() else "")
                                tables.append(tblnm)
                                for col in tk.data["fk"]["column"]:
                                    fks.append( tks_c[i+1].data["table"] + "." + col)
                                tblnm = tk.data["fk"]["alias"] if "alias" in tk.data["fk"].keys() else  tk.data["fk"]["table"]
                                fields.append(tblnm + "." + column)
                            else: # this is a table
                                if(column == "*"):
                                    fields.append("distinct " + tk.data["table"] + "." + column)
                                else:
                                    fields.append(tk.data["table"] + "." + column)
                                tables.append(tk.data["table"])
                                tables_nofks.append(tk.data["table"])
                                if 'where' in tk.data:
                                    fks.append(tk.data["where"])

                        if( i == 2  ): # it is a table
                            tables.append(tk.data["table"])
                            tables_nofks.append(tk.data["table"])
                            if 'where' in tk.data:
                                fks.append(tk.data["where"])


            except Exception as e:
                print(e)

        tables = list(set(tables))

        return {"tables":tables, "fks":fks, "fields":fields, "tables_nofks" : tables_nofks}

    def table_name(self, tk):    
        """ Table name for a foreign key
        """
        return tk.data["fk"]["table"] + (( " as " + tk.data["fk"]["alias"]) if "alias" in tk.data["fk"].keys() else "")

    def query_check(self,fields, conditions=""):  
        """No more than one table (excluding fks)
        """
        
        select = self.parse(fields)
        where = self.parse(conditions)

        tables = select["tables_nofks"] + where["tables_nofks"]
        tables = list(set(tables))
        #print("query check",fields,select, tables)
        
        if(len(tables) != 1): return False

        return True

    def query_desc(self,fields, conditions=""):
        if(self.force_clean ):
            fields = self.clean_query(fields)
            conditions = self.clean_query(conditions)

        select = self.parse(fields)
        where = self.parse(conditions)
        tables = select["tables"] + where["tables"]
        fks = select["fks"] + where["fks"]

        desc = self.foreign_keys(tables, fks)["desc"]
        return "\n".join(desc)


    def foreign_keys(self, tables, fks):
        desc = []

        return { "fks":fks, "desc":desc} 

        # force fk for queries on multiple tables. In case of multiple insertions, the doublers are removed below  
        #  PARENT_LEVEL = LEVEL('{"column" : "parent_l_seqno", "fk": {"table" : "levels", "alias" : "levels_s" , "column" : ["parent_l_seqno = levels_s.l_seqno", "parent_nucid = levels_s.nucid"]}}')
        if LEVEL.data["table"] in tables and NUCLIDE.data["table"] in tables:
                fks.append("nuclides.nucid = levels.nucid")
                desc.append(" nuclide having the level")

# think more about
        if (self.table_name(DR_GAMMA.END_LEVEL))  in tables and NUCLIDE.data["table"] in tables:    
                fks.append("gammas.nucid = "+ DR_GAMMA.END_LEVEL.data["fk"]["alias"] + ".nucid")
               
# this is ambiguous, it could link to the daughter        
        if DR_GAMMA.data["table"] in tables and NUCLIDE.data["table"] in tables:
            fks.append("nuclides.nucid = dr_gammas.parent_nucid")
            desc.append(" the parent of the nuclide emitting the radiation")


        if GAMMA.data["table"] in tables and NUCLIDE.data["table"] in tables:
            print("found")
            fks.append("nuclides.nucid = gammas.nucid")
            desc.append(" nuclide having the gamma transition")

        if GAMMA.data["table"] in tables and LEVEL.data["table"] in tables:
            fks.append("levels.nucid = gammas.nucid")
            fks.append("levels.l_seqno = gammas.l_seqno")
            desc.append(" level emitting the gamma")


# consider whether to add the level
        if GAMMA.data["table"] in tables and L_DECAY.data["table"] in tables:
            fks.append("l_decays.nucid = gammas.nucid")
            desc.append(" parent nuclide having the gamma")

            #fks.append("l_decays.l_seqno = gammas.l_seqno")

        if GAMMA.data["table"] in tables and _DECAY_RADIATION.data["table"] in tables:
            fks.append("decay_radiations.daughter_nucid = gammas.nucid")
            fks.append("decay_radiations.adopted_daughter_l_seqno = gammas.l_seqno")
            desc.append(" daughter having the gamma ")

        # link to parent or daughter ?
        # if L_DECAY.data["table"] in tables and NUCLIDE.data["table"] in tables:
        #     fks.append("nuclides.nucid = l_decays.nucid")
        #     desc.append(" parent nuclide of the decay")

        # link to parent or daughter ?
        # if L_DECAY.data["table"] in tables and LEVEL.data["table"] in tables:
        #     fks.append("levels.nucid = l_decays.nucid")
        #     fks.append("levels.l_seqno = l_decays.l_seqno")
        #     desc.append(" parent level of the decay")


        # in the dr there are two possible reference : parent or daughter
        # if _DR_BASE.data["table"] in tables and NUCLIDE.data["table"] in tables:
        #     fks.append("nuclides.nucid = decay_radiations.parent_nucid")
        #     desc.append(" parent nuclide of the decay")
            

        if CUM_FY.data["table"] in tables and DR_GAMMA.data["table"] in tables:
            fks.append("cum_fy.daughter_nucid = dr_gammas.parent_nucid")
            desc.append(" product nuclide whose decay daughter emits the gamma")

        return { "fks":fks, "desc":desc} 




    def query_build(self,fields, conditions=""):

        if(self.force_clean ): # place spaces around orm tokens
            fields = self.clean_query(fields)
            conditions = self.clean_query(conditions)

        select = self.parse(fields)
        fields_str = " ".join(select["fields"])

        where = self.parse(conditions)

        tables = select["tables"] + where["tables"]
        fks = select["fks"] + where["fks"]

        fks = self.foreign_keys(tables, fks)["fks"]

        tables = list(set(tables)) # remove doublers
        tables_str = ",".join(tables)

        fks = list(set(fks))
        fks_str = " and ".join(fks)

        where_str =  " ".join(where["fields"])

        if ( len(where_str) > 0 and len(fks_str) > 0 ):
            where_str = fks_str + " and " + where_str
        elif (len(fks_str) > 0):
            where_str = fks_str

        where_str = where_str.strip();
        if ( (not any([where_str.startswith(s) for s in ["order","group","having"]]) ) and (len(where_str) > 0 )) :
            where_str = "where " + where_str

        qry =  "select " + fields_str + " from " + tables_str + " " + where_str

        return qry

def description(obj):
         #classfact =  getattr(sys.modules[__name__], name)
         #obj = classfact()
         s = obj.__name__ + ": " + obj.desc + '\n\n'
         lst =  dir(obj)
         lst.sort()
         for att in lst:
            #if(att.upper() == att):
                try:
                    try:
                        dsc = getattr(obj, att).data["desc"]
                    except:
                        dsc = getattr(obj, att).desc 
                    if(dsc != ''):
                        s += att + (' \t\t' if len(att) < 7 else ' \t')+ dsc + '\n'
                except:
                    None

         return s

def description_html(obj):
         #classfact =  getattr(sys.modules[__name__], name)
         #obj = classfact()
         s = '<table><tr><th colspan=2>' + obj.__name__ + ": " + obj.desc + '</th></tr> \n' 
         lst =  dir(obj)
         lst.sort()
         for att in lst:
            #if(att.upper() == att):
                try:
                    try:
                        dsc = getattr(obj, att).data["desc"]
                    except:
                        dsc = getattr(obj, att).desc 
                    if(dsc != ''):
                        s += '<tr><td>' + att + '</td><td>'+ dsc + '</td></tr>\n'
                except:
                    None

         return (s + '</table>')

def description_sphinx(obj):
         nl = "| "
         nlb = "| **"
         eb = "** |nbspc| |nbspc| "
         s = obj.__name__  + '\n' + '------------------' + '\n\n'
         s += nl + obj.desc + '\n\n'
         lst =  dir(obj)
         lst.sort()
         for att in lst:
                try:
                    try:
                        dsc = getattr(obj, att).data["desc"]
                    except:
                        dsc = getattr(obj, att).desc 
                    if(dsc != ''):
                        s += nlb + att + eb + (' \t\t' if len(att) < 7 else ' \t')+ dsc + '\n'
                except:
                    None

         return s

def sphinx_guide():
    print(description_sphinx(NUCLIDE))
    print(description_sphinx(LEVEL))
    print(description_sphinx(GAMMA))
    print(description_sphinx(L_DECAY))

    print(description_sphinx(DR_ALPHA))

    # print(description_sphinx(DR_BETA))
    print(description_sphinx(DR_BETAM))
    print(description_sphinx(DR_BETAP))

    print(description_sphinx(DR_ANTI_NU))
    print(description_sphinx(DR_NU))

    print(description_sphinx(DR_DELAYED))

    print(description_sphinx(DR_GAMMA))
    print(description_sphinx(DR_PHOTON_TOTAL))

    print(description_sphinx(DR_X))
    print(description_sphinx(DR_AUGER))
    print(description_sphinx(DR_ANNIHIL))
    print(description_sphinx(DR_CONV_EL))

    print(description_sphinx(CUM_FY))
    print(description_sphinx(IND_FY))


_STR = '*(S)* '
_QTT = '*(Q)* '
_QTTL = '*(q)* '
_LNK = '*(L)* '

class _Base:
    
    ALL = json.loads('{"column" : "*"}')
    def __init__(self, data):
        if data == "":
            self.data = "{}"
        self.data = json.loads(data)  
        
class Column(_Base):
    def __init__(self,name, description = ''):
        super().__init__('{"column" : "' + name + '", "desc" : "' + description + '"}')

    @property
    def desc(self):
       try:
        #if self.data['column'].endswith('unc'): return 'uncertainty'
        #if self.data['column'].endswith('limit'): return 'GT for >, LE for <, ... '
        if(self.data['desc'] != ''):
            return  self.data['desc']
       except:
            return 'no' + self.data 

class NUCLIDE(_Base):
    desc =  "properties of the nuclide in its ground state"
    data = json.loads('{"table" : "nuclides"}')
    Z = Column('z','number of protons')
    N = Column('n', 'number of neutrons')
    NUC_ID = Column('nucid', _STR + 'identifier, e.g. 135XE') 
    ELEM_SYMBOL = Column('elem_symbol' , _STR + 'symbol of the element')
    CHARGE_RADIUS = Column('charge_radius', _QTT + 'Root-mean-square of the nuclear charge radius, expressed in fm. ')
    CHARGE_RADIUS_UNC = Column('charge_radius_unc')
    CHARGE_RADIUS_LIMIT = Column('charge_radius_limit')
    ATOMIC_MASS = Column('atomic_mass', _QTT + 'atomic mass, in micro AMU')
    ATOMIC_MASS_UNC = Column('atomic_mass_unc')
    ATOMIC_MASS_LIMIT = Column('atomic_mass_limit')
    MASS_EXCESS = Column('mass_excess', _QTT + 'mass excess [keV]')
    MASS_EXCESS_UNC = Column('mass_excess_unc')
    MASS_EXCESS_LIMIT = Column('mass_excess_limit')
    BINDING_EN = Column('binding_en',_QTT + 'binding energy per nucleon [keV]')
    BINDING_EN_UNC = Column('binding_en_unc')
    BINDING_EN_LIMIT = Column('binding_en_limit')
    BETA_DECAY_EN = Column('beta_decay_en', _QTT + 'energy available for beta decay [keV]')
    BETA_DECAY_EN_UNC = Column('beta_decay_en_unc')
    BETA_DECAY_EN_LIMIT = Column('beta_decay_en_limit')
    S2N = Column('s2n',_QTT + '2-neutron separation energy [keV]')
    S2N_UNC = Column('s2n_unc')
    S2N_LIMIT = Column('s2n_limit')
    S2P = Column('s2p',_QTT + '2-proton separation energy [keV]')
    S2P_UNC = Column('s2p_unc')
    S2P_LIMIT = Column('s2p_limit')
    QA = Column('qa',_QTT + 'alpha decay Q energy [keV]')
    QA_UNC = Column('qa_unc')
    QA_LIMIT = Column('qa_limit')
    QBMN = Column('qbmn',_QTT + 'beta- + n decay energy [keV]')
    QBMN_UNC = Column('qbmn_unc')
    QBMN_LIMIT = Column('qbmn_limit')
    SN = Column('sn',_QTT + 'neutron separation energy [keV]')
    SN_UNC = Column('sn_unc')
    SN_LIMIT = Column('sn_limit')
    SP = Column('sp',_QTT + 'proton separation energy [keV]')
    SP_UNC = Column('sp_unc')
    SP_LIMIT = Column('sp_limit')
    QEC = Column('qec',_QTT + 'electron capture Q-value [keV]')
    QEC_UNC = Column('qec_unc')
    QEC_LIMIT = Column('qec_limit')
    ABUNDANCE = Column('abundance',_QTTL + 'natural abundance, in mole fraction')
    ABUNDANCE_UNC = Column('abundance_unc')
   
    def __init__(self,name):
        super().__init__(name)
   
   

class LEVEL(_Base):
    desc =  "properties of the energy states of a nuclide"
    data = json.loads('{"table" : "levels"}')
    NUC = NUCLIDE('{ "column" : "nucid", "fk": {"table" : "nuclides", "alias" : "lev_nuc" , "column" : ["nucid = lev_nuc.nucid"]}, "desc" : "' + _LNK + '  access to the properties of the nuclide , e.g. LEVEL.NUC.Z  "}')
    SEQNO = Column('l_seqno','sequential number of the level, G.S. = 0')
    ENERGY = Column('energy',_QTT + 'level energy [keV]')
    ENERGY_UNC = Column('energy_unc')
    ENERGY_LIMIT = Column('energy_limit')
    HALF_LIFE = Column('half_life',_QTT + 'Half-life value as given in the evaluation, see HALF_LIFE_UNITS for the units. Use HALF_LIFE_SEC for calculations ')
    HALF_LIFE_UNC = Column('half_life_unc')
    HALF_LIFE_UNITS = Column('half_life_units', _STR +' the HALF-LIFE field units')
    HALF_LIFE_LIMIT = Column('half_life_limit', _STR +' - > , <, >=, etc..')
    HALF_LIFE_SEC = Column('half_life_sec',_QTT + 'H-l [s]')
    HALF_LIFE_SEC_UNC = Column('half_life_sec_unc')
    JP = Column('jp_str', _STR + 'Jp as given in the evaluation')
    J = Column('j','J value as assigned in RIPL')
    P = Column('parity','parity as assigned in RIPL')
    JP_ORDER = Column('jp_order','order of the Jp: 1 is the first occurence ')
    JP_REASON = Column('jp_reason','reason for assigning the Jp: JP_WEAK for weak arguments; JP_STRONG for strong')
    JP_METHOD = Column('jp_method','method for assigning the Jp with RIPL, see the RIPL_J_* values')
    QUADRUPOLE_EM = Column('quadrupole_em',_QTT + 'Electrinc quadrupole moment [b]')
    QUADRUPOLE_EM_UNC = Column('quadrupole_em_unc')
    QUADRUPOLE_EM_LIMIT = Column('quadrupole_em_limit')
    DIPOLE_MM = Column('dipole_mm',_QTT + 'magnetic dipole moment [Bohr magnetons]')
    DIPOLE_MM_UNC = Column('dipole_mm_unc')
    DIPOLE_MM_LIMIT = Column('dipole_mm_limit')
#    METASTABLE = Column('metastable', _STR + 'whether there is an evaluated decay mode with the list of radiations')
    QUESTIONABLE = Column('questionable', _STR + 'the existence of the level is questionable')
    CONFIGURATION = Column('configuration', _STR + 'the nuclear configuration')
    ISOSPIN = Column('isospin', _STR + 'Isospin')
    NUC_ID = Column('nucid')

    def __init__(self,name):
        super().__init__(name)

class DECAY_MODE(_Base):
    data = json.loads('{"table" : "decay_modes"}')
    NAME = Column('mode')
    CODE = Column('code')
    DESC = Column('desc')
    def __init__(self,name):
        super().__init__(name)


# extend to add the decay decode, decay group
class L_DECAY(_Base):
    desc = "properties of a decay mode of a level"
    data = json.loads('{"table" : "l_decays"}')
    NUC = NUCLIDE('{ "column" : "nucid", "fk": {"table" : "nuclides", "alias": "dec_p_nuc" , "column" : ["nucid = dec_p_nuc.nucid"]},  "desc" :  "' + _LNK + ' access to parent nuclide properties , e.g. L_DECAY.NUC.Z  "}')
    LEVEL = LEVEL('{"column" : "l_seqno", "fk": {"table" : "levels", "alias": "dec_p_lev" ,"column" : ["l_seqno = dec_p_lev.l_seqno", "nucid = dec_p_lev.nucid"]} , "desc" :  "' + _LNK + ' access to the properties of the level, e.g. L_DECAY.LEVEL.ENERGY  "}')
    MODE = Column('decay_code','code of the decay, specify it  using one of the DECAY_* constants')
#    MODE = DECAY_MODE('{"column" : "decay_code", "fk": {"table" : "decay_modes", "column" : ["decay_code = decay_modes.code "]}, "desc" : "decay mode"}')
#    MODE = _Base('{"column" : "decay_code", "fk": {"table" : "decay_codes", "column" : ["decay_codes.decay_code = decay_code"]}, "desc" : "decay mode code"}')
    DAUGHTER = NUCLIDE('{ "column" : "daughter_nucid", "fk": {"table" : "nuclides", "alias": "dec_d_nuc" , "column" : ["daughter_nucid = dec_d_nuc.nucid"]}, "desc" :  "' + _LNK + ' access to daughter nuclide properties , e.g. L_DECAY.DAUGHTER.Z  "}')
    PERC = Column('perc',_QTT + 'decay probability per 100 decays of the parent')
    PERC_UNC = Column('perc_unc')
    PERC_LIMIT = Column('perc_limit')
    Q_TOGS = Column('q_togs',_QTTL + 'Q-value of the decay. For decay of isomeric sates, it includes the parent energy level')
    Q_TOGS_UNC = Column('q_togs_unc')

    NUC_ID = Column('nucid')
    LEVEL_SEQNO =  Column('l_seqno')
    DAUGHTER_NUC_ID = Column('daughter_nucid')
   

    def __init__(self,name):
        super().__init__(name)

class _GM(_Base):  
    data = json.loads('{"table" : ""}')
    START_LEVEL = LEVEL('{"column" : "l_seqno", "fk": {"table" : "levels", "alias" : "gam_lev_s" , "column" : ["l_seqno = gam_lev_s.l_seqno", "nucid = gam_lev_s.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the start level, e.g. GAMMA.START_LEVEL.ENERGY  "}')
    END_LEVEL = LEVEL('{"column" : "final_l_seqno", "fk": {"table" : "levels", "alias" : "gam_lev_e" , "column" : ["final_l_seqno = gam_lev_e.l_seqno", "nucid = gam_lev_e.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the end level, e.g. GAMMA.END_LEVEL.ENERGY  "}')
    SEQNO = Column('g_seqno', 'sequential number of the gamma with respect to the start level, 0 being the gamma with the lowest energy')
    ENERGY = Column('energy', _QTT + ' energy [keV]')
    ENERGY_UNC = Column('energy_unc')
    ENERGY_LIMIT = Column('energy_limit')
    REL_PHOTON_INTENS = Column('rel_photon_intens', _QTT + 'relative photon intensity [%]. The sum over the same start level is 100')
    REL_PHOTON_INTENS_UNC = Column('rel_photon_intens_unc')
    REL_PHOTON_INTENS_LIMIT = Column('rel_photon_intens_limit')
    MULTIPOLARITY = Column('multipolarity','String - multipolarity')
    MIXING_RATIO = Column('mixing_ratio', _QTT + 'mixing ratio')
    MIXING_RATIO_UNC = Column('mixing_ratio_unc')
    MIXING_RATIO_LIMIT = Column('mixing_ratio_limit')
    TOT_CONV_COEFF = Column('tot_conv_coeff', _QTT + 'total conversion coefficient')
    TOT_CONV_COEFF_UNC = Column('tot_conv_coeff_unc')
    TOT_CONV_COEFF_LIMIT = Column('tot_conv_coeff_limit')
    BEW = Column('bew', _QTT + 'reduced electric transition probabilities in Weisskopf units')
    BEW_UNC = Column('bew_unc')
    BEW_LIMIT = Column('bew_limit')
    BEW_ORDER = Column('bew_order','order of the transition')
    BMW = Column('bmw', _QTT + 'reduced magnetic transition probabilities in Weisskopf units')
    BMW_UNC = Column('bmw_unc')
    BMW_LIMIT = Column('bmw_limit')
    BMW_ORDER = Column('bmw_order','order of the transition')
    QUESTIONABLE = Column('questionable', _STR + 'the existence is questionable')

    START_LEVEL_SEQNO = Column('l_seqno')
    END_LEVEL_SEQNO = Column('final_l_seqno')

class GAMMA(_GM):
    desc =  "properties of a nuclide electromagnetic transition"
    data = json.loads('{"table" : "gammas"}')

    NUC = NUCLIDE( '{"column" : "nucid", "fk":{"table" : "nuclides", "alias" : "gam_nuc"    , "column" : ["nucid=gam_nuc.nucid"]}, "desc" : "* Link - access to the properties of the nuclide, e.g. GAMMA.NUC.Z  "}')
    NUC_ID = Column('nucid')
   # def __init__(self,name):
   #     super().__init__(name)

class _DR_BASE(_Base):
    desc =  "properties the decay radiation"
    data = json.loads('{"table" : "decay_radiations"}')
    PARENT = NUCLIDE( '{"column" : "parent_nucid", "fk":{"table" : "nuclides", "alias" : "dr_nuc_p","column" : ["parent_nucid=dr_nuc_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the parent nuclide, e.g. DR_*.PARENT.Z  "}')
    PARENT_LEVEL = LEVEL('{"column" : "parent_l_seqno", "fk": {"table" : "levels", "alias" : "dr_lev_p" , "column" : ["parent_l_seqno = dr_lev_p.l_seqno", "parent_nucid = dr_lev_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the parent level, e.g. DR_*.PARENT_LEVEL.ENERGY  "}')
    DAUGHTER = NUCLIDE( '{"column" : "daughter_nucid", "fk":{"table" : "nuclides", "alias" : "dr_nuc_d" , "column" : ["daughter_nucid=dr_nuc_d.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the daughter nuclide, e.g. DR_*.DAUGHTER.ENERGY  "}')
    DAUGHTER_FED_LEVEL = LEVEL('{"column" : "adopted_daughter_l_seqno", "fk": {"table" : "levels", "alias" : "dr_lev_d" , "column" : ["adopted_daughter_l_seqno = dr_lev_d.l_seqno", "parent_nucid = dr_lev_d.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the level in which the daughter nuclide is created , e.g. DR_*.DAUGHTER_FED_LEVEL.ENERGY  "}')
    MODE = Column('decay_code','code of the decay, specify it  using one of the DECAY_* constants') 
    INTENSITY_= Column('intensity', _QTT + 'absolute intensity of the radiation per 100 decays of the parent')
    INTENSITY_UNC = Column('intensity_unc')
    INTENSITY_LIMIT = Column('intensity_limit')
    ENERGY = Column('energy', _QTT + 'energy of the radiation [keV]')
    ENERGY_UNC = Column('energy_unc')
    ENERGY_LIMIT = Column('energy_limit')
    
    PARENT_NUC_ID = Column('parent_nucid')
    PARENT_LEVEL_SEQNO = Column('parent_l_seqno')
    DAUGHTER_NUC_ID = Column('daughter_nucid')
    DAUGHTER_FED_LEVEL_SEQNO = Column('adopted_daughter_l_seqno')



class _FY(_Base):
    
    data = json.loads('{"table" : "cum_fy"}')

    THER_YIELD = Column('ther_yield', _QTTL + 'thermal neutron yield')
    THER_YIELD_UNC = Column('ther_yield_unc')
    FAST_YIELD = Column('fast_yield_num', _QTTL + 'fast neutron yield')
    FAST_YIELD_UNC = Column('fast_yield_unc')
    MEV_14_YIELD = Column('mev_14_yield', _QTTL + '14 MeV neutron yield')
    MEV_14_YIELD_UNC = Column('mev_14_yield_unc')

    PARENT_NUC_ID =  Column('parent_nucid')
    PRODUCT_NUC_ID =  Column('daughter_nucid')
    PARENT_LEVEL_SEQNO = Column('l_seqno')

class CUM_FY(_FY):
    desc =  "cumulative fission yields"
    PARENT = NUCLIDE( '{"column" : "parent_nucid", "fk":{"table" : "nuclides", "alias" : "cfy_nuc_p", "column" : ["parent_nucid=cfy_nuc_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the fissioning nuclide, e.g. CUM_FY.PARENT.Z  "}')
    PRODUCT = NUCLIDE( '{"column" : "daughter_nucid", "fk":{"table" : "nuclides", "alias" : "cfy_nuc_d", "column" : ["daughter_nucid=cfy_nuc_d.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the product nuclide, e.g. CUM_FY.PRODUCT.Z  "}')
    PARENT_LEVEL = LEVEL('{"column" : "l_seqno", "fk": {"table" : "levels", "alias" : "cfy_lev_p" , "column" : ["parent_l_seqno = cfy_lev_p.l_seqno", "parent_nucid = cfy_lev_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the parent level, e.g. CUM_FY.PARENT_LEVEL.ENERGY  "}')


    def __init__(self,name):
        super().__init__(name)

class IND_FY(_FY):
    desc =  "independent fission yields"
    data = json.loads('{"table" : "ind_fy"}')
    PARENT = NUCLIDE( '{"column" : "parent_nucid", "fk":{"table" : "nuclides", "alias" : "ify_nuc_p", "column" : ["parent_nucid=ify_nuc_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the fissioning nuclide, e.g. IND_FY.PARENT.Z  "}')
    PRODUCT = NUCLIDE( '{"column" : "daughter_nucid", "fk":{"table" : "nuclides", "alias" : "ify_nuc_d","column" : ["daughter_nucid=ify_nuc_d.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the product nuclide, e.g. IND_FY.PRODUCT.Z  "}')
    PARENT_LEVEL = LEVEL('{"column" : "l_seqno", "fk": {"table" : "levels", "alias" : "ify_lev_p" , "column" : ["parent_l_seqno = ify_lev_p.l_seqno", "parent_nucid = ify_lev_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the parent level, e.g. IND_FY.PARENT_LEVEL.ENERGY  "}')


    
    def __init__(self,name):
        super().__init__(name)

class DR_ALPHA(_DR_BASE):
    desc =  "alpha decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a=\'A\'"}')
    HINDRANCE = Column('a_hindrance', _QTT + 'hindrance factor')
    HINDRANCE_UNC = Column('a_hindrance_unc')
    HINDRANCE_LIMIT = Column('a_hindrance_limit')

    def __init__(self,name):
        super().__init__(name)

class DR_BETA(_DR_BASE):
    """docstring for ."""

    data = json.loads('{"table" : "decay_radiations", "where" :"(type_a=\'B+\' or type_a=\'B-\')"}')

    LOGFT = Column('b_logft', _QTT + 'log ft')
    LOGFT_UNC = Column('b_logft_unc')
    LOGFT_LIMIT = Column('b_logft_limit')

    TRANS_TYPE = Column('b_trans_type',  _STR + "transition type, specfy it using one of the TRANS_TYPE_* constants")

    ENDPOINT = Column('b_endpoint', _QTT + 'end-point energy [keV]')
    ENDPOINT_UNC = Column('b_endpoint_unc')
    ENDPOINT_LIMIT = Column('b_endpoint_limit')


    def __init__(self, name):
        super().__init__(name)
       


class DR_BETAP(DR_BETA):
    desc =  "beta+ decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a=\'B+\'"}')

    EC_ENERGY = Column('ec_energy', _QTT + 'energy available for electron capture')
    EC_ENERGY_UNC = Column('ec_energy_unc')
    EC_ENERGY_LIMIT = Column('ec_energy_limit')

    BPEC_INTENSITY = Column('bpec_intensity', _QTT + 'sum of electron capture and beta+ intensites per 100 decays of the parent')
    BPEC_INTENSITY_UNC = Column('bpec_intensity_unc')
    BPEC_INTENSITY_LIMIT = Column('bpec_intensity_limit')

    EC_INTENSITY = Column('ec_intensity', _QTT + 'electron capture intensity per 100 decays of the parent')
    EC_INTENSITY_UNC = Column('ec_intensity_unc')
    EC_INTENSITY_LIMIT = Column('ec_intensity_limit')

    def __init__(self,name):
        super().__init__(name)

class DR_BETAM(DR_BETA):
    desc =  "beta- decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a=\'B-\'"}')

    def __init__(self,name):
        super().__init__(name)

class DR_ANTI_NU(_DR_BASE):
    desc =  "anti neutrino decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a=\'B-\'"}')
    ENERGY_LIMIT = Column('energy_nu_limit')
    ENERGY = Column('energy_nu', _QTT + 'energy [keV]')
    ENERGY_UNC = Column('energy_nu_unc')
    def __init__(self,name):
        super().__init__(name)

class DR_NU(DR_ANTI_NU):
    desc =  "neutrino decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a=\'B+\'"}')
    ENERGY_EC = Column('energy_ec', _QTTL + 'energy [keV]')
    ENERGY_EC_UNC = Column('energy_ec_unc')
    def __init__(self,name):
        super().__init__(name)

class DR_DELAYED(_DR_BASE):
    desc =  "delayed particle emission"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a in (\'DN\',\'DP\',\'DA\')"}')

    TYPE = Column('type_a',  _STR + 'delayed particle: DN, DP, or DA')
    ENERGY_X = Column('d_energy_x', _QTT + 'energy of the intermediate state after beta decay and before emetting the particle [keV]')
    ENERGY_X_UNC = Column('d_energy_x_unc')
    ENERGY_X_LIMIT = Column('d_energy_x_limit')

    def __init__(self,name):
        super().__init__(name)

class DR_PHOTON_TOTAL(_Base):
    desc =  "photon decay radiation (regardless whether gamma or X)"
    data = json.loads('{"table" : "dr_photon_totals"}')
                                                                                                                                                                                  
    PARENT = NUCLIDE( '{"column" : "parent_nucid", "fk":{"table" : "nuclides","alias" : "pt_nuc_p" ,  "column" : ["parent_nucid=pt_nuc_p.nucid"]},"desc": "' + _LNK + ' access to the properties of the parent nuclide, e.g. DR_*.PARENT.Z  "}')
    PARENT_LEVEL = LEVEL('{"column" : "parent_l_seqno", "fk": {"table" : "levels", "alias" : "pt_lev_p" , "column" : ["parent_l_seqno = pt_lev_p.l_seqno", "parent_nucid = pt_lev_p.nucid"]}, "desc" :  "' + _LNK + ' access to the properties of the parent level, e.g. DR_*.PARENT_LEVEL.ENERGY  "}')

    ENERGY = Column('energy', _QTTL + 'energy [keV]')
    ENERGY_UNC = Column('energy_unc')
    INTENSITY = Column('intensity', _QTTL + 'intensity per 100 dcay of the parent')
    INTENSITY_UNC = Column('intensity_unc')
    
    COUNT = Column('cnt','number of parent decay mode is which the line is present ')
    TYPE = Column('type', _STR + 'whether X or G')

    PARENT_NUC_ID =  Column('parent_nucid')
    PARENT_LEVEL_SEQNO = Column('parent_l_seqno')

    def __init__(self,name):
        super().__init__(name)
 

class DR_GAMMA(_GM):
    desc =  "gamma decay radiation"
    data = json.loads('{"table" : "dr_gammas"}')


    PARENT = NUCLIDE( '{"column" : "parent_nucid", "fk":{"table" : "nuclides","alias" : "drg_nuc_p" ,  "column" : ["parent_nucid=drg_nuc_p.nucid"]} ,"desc": "' + _LNK + ' access to the properties of the parent nuclide, e.g. DR_GAMMA.PARENT.Z  "}')
    PARENT_LEVEL = LEVEL('{"column" : "parent_l_seqno", "fk": {"table" : "levels", "alias" : "drg_lev_p" , "column" : ["parent_l_seqno = drg_lev_p.l_seqno", "parent_nucid = drg_lev_p.nucid"]},"desc": "' + _LNK + '  access to the properties of the parent level, e.g. DR_GAMMA.PARENT_LEVEL.ENERGY  "}')
    MODE = Column('decay_code','code of the decay, specify it  using one of the DECAY_* constants') 
    INTENSITY = Column('intensity', _QTT + 'intensity per 100 dcay of the parent')
    INTENSITY_UNC = Column('intensity_unc')
    INTENSITY_LIMIT = Column('intensity_limit')

    PARENT_NUC_ID =  Column('parent_nucid')
    PARENT_LEVEL_SEQNO = Column('parent_l_seqno')

    def __init__(self,name):
        super().__init__(name)

class _DR_ATOMIC(_DR_BASE):
    desc = ''
    SHELL = Column('type_c',  _STR + 'Atomic shell IUPAC notation, use one of the SHELL_* constants' )


class DR_X(_DR_ATOMIC):
    desc =  "X decay radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a = \'G\' and type_b=\'X\'"}')

    def __init__(self,name):
        super().__init__(name)

class DR_CONV_EL(_DR_ATOMIC):
    desc =  "conversion electron  radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a = \'E\' and type_b=\'CE\'"}')

    def __init__(self,name):
        super().__init__(name)

class DR_AUGER(_DR_ATOMIC):
    desc =  "Auger electron  radiation"
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a = \'E\' and type_b=\'AU\'"}')
   
    def __init__(self,name):
        super().__init__(name)

class DR_ANNIHIL(_DR_BASE):
    desc =  "gamma from annihilation "
    data = json.loads('{"table" : "decay_radiations", "where" :"type_a = \'G\' and type_b=\'AN\'"}')

    def __init__(self,name):
        super().__init__(name)

# decay codes
DECAY_A = 0
DECAY_Bp = 1
DECAY_Bm = 2
DECAY_IT = 3
DECAY_P = 4
DECAY_N = 5
DECAY_BmN = 6
DECAY_EC = 7
DECAY_SF = 8
DECAY_D = 9
DECAY_ECP = 10
DECAY_3HE = 11
DECAY_BpP = 12
DECAY_3H = 13
DECAY_G = 14
DECAY_Bp = 15
DECAY_ECA = 16
DECAY_Bm2N = 17
DECAY_8BE = 18
DECAY_BpA = 19
DECAY_2Bm = 20
DECAY_2P = 21
DECAY_BmA = 22
DECAY_14C = 23
DECAY_EC2P = 24
DECAY_Bp2P = 25
DECAY_2Bp = 26
DECAY_28MG = 27
DECAY_ECSF = 28
DECAY_Bm3N = 29
DECAY_2EC = 30
DECAY_24NE = 31
DECAY_ECF = 32
DECAY_NE = 33
DECAY_ECP_EC2P = 34
DECAY_22NE = 35
DECAY_34SI = 36
DECAY_EC_SF = 37
DECAY_24NE = 38
DECAY_BF = 39
DECAY_SF_EC_Bp = 40
DECAY_SF_Bm = 41
DECAY_Bm4N = 42
DECAY_SF_EC_Bm = 44
DECAY_IT_EC_Bp = 45
DECAY_EC3P = 46
DECAY_20NE = 47
DECAY_BmF = 49
DECAY_BpEC = 50
DECAY_20O = 51
DECAY_MG = 52
DECAY_ECAP = 53
DECAY_2e = 54
DECAY_BmP = 55
DECAY_12C = 57
DECAY_25NE = 58
DECAY_34SI = 59
DECAY_22NE = 60
DECAY_2N = 61
DECAY_EC_SF = 62
DECAY_SF_EC_Bp = 63
DECAY_Bp3P = 46
DECAY_BmSF = 64
DECAY_Bm5N = 65
DECAY_BpF = 66
DECAY_28MG = 67
DECAY_Bm6N = 68
DECAY_Bm7N = 69

# delayed particle
DELAY_N = 'DN'
DELAY_A = 'DA'
DELAY_P = 'DP'

# ensdf JP assignment
JP_STRONG = 0
JP_WEAK = 1

# ripl J assignment methods
RIPL_J_UNKNOWN = -1
RIPL_J_UNIQUE = 0
RIPL_J_DISTRIBUTION_GAMMA = 1
RIPL_J_DISTRIBUTION = 2
RIPL_J_DISTRIBUTION_CONSTRAIN = 3

# ripl parity codes
RIPL_P_PLUS = 1
RIPL_P_MINUS = 0

# beta transition types
TRANS_1NU = '1NU'
TRANS_1U = '1U'
TRANS_2NU = '2NU'
TRANS_2U = '2U'
TRANS_3NU = '3NU'
TRANS_3U = '3U'
TRANS_4NU = '4NU'
TRANS_4U = '4U'
TRANS_5NU = '5NU'
TRANS_5U = '5U'
TRANS_7NU = '7NU'
TRANS_8U = '8U'
TRANS_A = 'A'
TRANS_S = 'S'


SHELL_K = 'K'
SHELL_KA1 = 'KA1'
SHELL_KA2 = 'KA2'
SHELL_KB = 'KB'
SHELL_KLL = 'KLL'
SHELL_KLX = 'KLX'
SHELL_KXY = 'KXY'
SHELL_KpB1 = 'KpB1'
SHELL_KpB2 = 'KpB2'
SHELL_L = 'L'
SHELL_L1 = 'L1'
SHELL_L1M2 = 'L1M2'
SHELL_L1M3 = 'L1M3'
SHELL_L1N2 = 'L1N2'
SHELL_L1N3 = 'L1N3'
SHELL_L1O23 = 'L1O23'
SHELL_L2 = 'L2'
SHELL_L2M1 = 'L2M1'
SHELL_L2M4 = 'L2M4'
SHELL_L2N1 = 'L2N1'
SHELL_L2N4 = 'L2N4'
SHELL_L2O1 = 'L2O1'
SHELL_L2O4 = 'L2O4'
SHELL_L3 = 'L3'
SHELL_L3M1 = 'L3M1'
SHELL_L3M4 = 'L3M4'
SHELL_L3M5 = 'L3M5'
SHELL_L3N1 = 'L3N1'
SHELL_L3N45 = 'L3N45'
SHELL_L3O1 = 'L3O1'
SHELL_L3P1 = 'L3P1'
SHELL_M = 'M'
SHELL_N = 'N'
SHELL_NPLUS = 'N+'
SHELL_O = 'O'

def get_const():
      
        import ndlabdblink as dl
        dbl = dl.Dblink('ndlab_db.s3db')
        
        lst = []
        for i in range(0,70):
            lst.append('')


        for name, obj in inspect.getmembers(sys.modules["ndlaborm"]):
            if name.startswith('DECAY') and not name.startswith('DECAY_MODE'):
                property = getattr(sys.modules[__name__],name)
                print(name, property)
                sql = ("select '" + name + "', desc from decay_modes where code="+str(property))
                rs = dbl._cur_lite.execute(sql)
                for r in rs:
                    print('| **' +r[0]+'**' + ' = ' + str(property) + '  ' + r[1])
                    lst[property] = '| **' +r[0]+'**' + ' = ' + str(property) + '  ' + r[1]
        
        for l in lst:
            print(l)
                    
            
                
       



          