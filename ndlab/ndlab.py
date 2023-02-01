
"""
The user entry point to interrogate the database, and to write custom software

Direct database interrogation is through :py:meth:`ndlab.csv_data`, :py:meth:`ndlab.json_data`, :py:meth:`ndlab.csv_nl`,
:py:meth:`ndlab.pandas_csv_nl`, :py:meth:`ndlab.pandas_csv_web`.

For how to specify the query parameters, see :py:mod:`ndlaborm`

The  :py:class:`ndlab.Property`,  :py:class:`ndlab.Nominal`, :py:class:`ndlab.Quantity` implement the ISO Vocabulary (VIM) 
https://www.iso.org/sites/JCGM/VIM/JCGM_200e_FILES/MAIN_JCGM_200e/Start_e.html using also :py:class:`ndlab.Operator` and :py:class:`ndlab.Unit`


- The :py:class:`ndlab.Quantity` is the most relevant, and it embeds the uncerainities propagation using the 'uncertainities' packages 
  (https://pythonhosted.org/uncertainties/).
- A Quantity is initialised with  a json structure.
- The classes representing the model contain variables of type Quantity to store the data


The Base for the classes of the  nuclear model is  :py:class:`ndlab.NdmBase`. Their instance variables are intialized with a json structure
that is passed to each of their instance variables of type :py:class:`ndlab.Quantity` 

A set of functions initialize these classes querying the database through http 


"""

from __future__ import annotations
from gc import DEBUG_LEAK

from re import I
import io
import json
import copy

import ndlabdblink as dl
import sys

# the uncertainities (https://pythonhosted.org/uncertainties/)
from uncertainties import *  #

this = sys.modules[__name__]

db_path = 'ndlab_db.s3db'
dblink = dl.Dblink(db_path)

_filter = ""

DEFAULT = "NO_PARAM";
last_fields = ''
last_filter = ''

CSV_SEP = ','
ERROR_FILTER_NOT_VALID = "Fields or Filter not valid, check the rules"


def _float_check(val):
    """ Check if a value retrieved from the database is a float

    Args: 
        val:  (anything, most likey a string)

    Returns: 
        float: the string converted to float
        or
        None: no conversion to float possible    
    """
    try:
        return float(val)
    except:
        return None

def _int_check(val):
    """ Check if a value retrieved from the database is an integer

    Args: 
        val (int): The object to be converted

    Returns: 
        integer: the string converted to integer
        or
        None: no conversion to float possible    
    """

    try:
        return int(val)
    except:
        return None
    
def _str_check(val):
     if (str(val) == 'None'):
        return None
     return val

class Property:
    """ Models the ISO VIM

    Upper class with only the name of the property
    """

    def __init__(self, name = ''):
        self.name = name
       

    @property
    def name(self):
        """
        The name of the property

        Returns:
            String: name
        """
        return self._name_
    @name.setter
    def name(self, name):
        """
        Sets name of the property

        Args:
            name (str) : the name of the propery

        """
        self._name_= name

class Nominal(Property):
    """ Models the ISO VIM

    Quantities without magnitude
    """
#    value = None
    def __init__(self, name = ''):
        super(Nominal, self).__init__(name)

class Operator:
    """Qualifier of a value, e.g. >

    Contains the allowed modifiers and the rules of composition to handle matemathical operations between quantities
    
    """
    lt = "<"
    gt = ">"
    eq = "="
    ge = ">="
    le = "<="
    approx = "~"
    calculated = "CA"
    problem = "?"

    def compose(oa, ob):
        """ Rule for operators composition

        Args:
            oa (Operator): operator of the first quantity
            ob (Operator): operator of the second quantity

        Returns:
            Operator: oa composed with ob

        """

        if(oa == Operator.eq and ob == Operator.eq):
            return Operator.eq

        if( (oa == Operator.lt or oa == Operator.le or oa == Operator.eq) and (ob == Operator.lt or ob == Operator.le or ob == Operator.eq)):
            return Operator.lt
        if( (oa == Operator.gt or oa == Operator.ge or oa == Operator.eq) and (ob == Operator.gt or  ob == Operator.ge or ob == Operator.eq)):
            return Operator.gt

        # symmetric below
        if( oa == Operator.approx and ob != Operator.eq):
            return ob
        if( oa == Operator.approx and ob == Operator.eq):
            return oa

        if( ob == Operator.approx and oa != Operator.eq):
            return oa
        if( ob == Operator.approx and oa == Operator.eq):
            return ob

        if(oa == Operator.calculated or ob == Operator.calculated):
            return Operator.calculated

        return Operator.problem

    def test():
        ll = [Operator.approx,Operator.eq, Operator.ge,Operator.gt,Operator.le,Operator.lt,Operator.problem]
        for o1 in ll:
            for o2 in ll:
                print (o1, o2,Operator.compose(o1,o2))

class Unit:
    """Units of measure
    """
    normalized = "normalized"
    kev = "keV"
    mev = "MeV"
    amu = "AMU"
    mu_amu = "micro AMU"

class Quantity(Nominal):
    """Models the ISO VIM and handles the uncertainties propagation with ufloat from the `uncertainties <https://pythonhosted.org/uncertainties/>`__ package

     Attributes:
        sep (string):    The CSV separator to be used when dumping to CSV

     :ivar string nominal: name
     :ivar float value: float value
     :ivar string unc: uncertainity as string
     :ivar float  unc_num: uncertainity as float
     :ivar Operator: Operator
    """


    sep = CSV_SEP
    # name is the key to be used in populate
    def __init__(self, name = ''):
        super(Quantity, self).__init__(name)
        self.value = None
        self.unc_num = None
        self.unc = None
        self.operator = Operator.eq

    def _populate(self,data):
        """using a json structure. Fills the instance variables from a json structure:

        | value = data[{name}]
        | unc   = data[{name}_unc]
        | operator = data[{name}_limit]

        Args:
            data (json): data structure to fill the instance variables
        
        Returns:
            self: instance of the class
        
        """

        if self.name in data:
            self.nominal = data[self.name ]
            if(data[self.name] != 'None'):
                self.value = _float_check(data[self.name])
       
        if self.name + "_unc" in data:
            self.unc = (data[self.name+ "_unc"])
            if(data[self.name + "_unc"] != 'None'):
                self.unc_num = _float_check(data[self.name + "_unc"])
            else:
                self.unc = "0"
                self.unc_num = 0
 
        if self.name + "_limit" in data:
            self.operator = data[self.name + "_limit"]
            if (self.operator == ''):
                  self.operator = Operator.eq

        if self.value == None:
            self.value = 0;
            isnull = True

        self.unc_num = 0 if self.unc_num == None else self.unc_num;
        return self

    def ufloat(self):
        """ ufloat of the `uncertainties <https://pythonhosted.org/uncertainties/`__ package from :py:attr:`value` and :py:attr:`uncertainty` 
        """
        if(self.value is None):
            return None
        return ufloat(self.value, self.unc_num if self.unc_num is not None else 0)


    def create( value, unc, operator = Operator.eq):
        """ Creates a Quantity from a value, and uncertainty, and an operator.

        Used internally from overloaded mathematical functions

        Args:
            value (float): value
            unc (float): uncertainty
            operator (Operator): operator
        """
        q = Quantity()
        q.value = value
        q.unc = unc
        q.unc_num = unc
        q.operator = operator
        return q
    
    def csv(self):
        """Generates the CSV representation of the quantity
        
        Returns:
        String: the CSV
        """
        return str(self.value) + self.sep + str(self.unc) + self.sep + str(self.operator )

    def __add__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = self.ufloat() + qtt
        else:
            sm = self.ufloat() + qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __radd__(self,qtt):
        return self + qtt

    def __sub__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = self.ufloat() - qtt
        else:
            sm = self.ufloat() - qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __rsub__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = qtt - self.ufloat()
        else:
            sm =  qtt.ufloat() - self.ufloat() 
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))        

    def __mul__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = self.ufloat() * qtt
        else:
            sm = self.ufloat() * qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __rmul__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = self.ufloat() * qtt
        else:
            sm = self.ufloat() * qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __truediv__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm = self.ufloat() / qtt
        else:
            sm = self.ufloat() / qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))
        
    def __rtruediv__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            sm =  qtt / self.ufloat()
        else:
            sm =  qtt.ufloat() / self.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __pow__(self,qtt):
        op = Operator.eq
        if(qtt.__class__.__name__ != "Quantity"):
            if(qtt.__class__.__name__ != "Variable"):
                sm = self.ufloat() ** ufloat(qtt,0)
            else:
                sm = self.ufloat() ** qtt
        else:
            sm = self.ufloat() ** qtt.ufloat()
            op = qtt.operator
        return Quantity.create(sm.n, sm.s, Operator.compose(self.operator, op))

    def __lt__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() < other)
        else:
             return (self.ufloat() < other.ufloat())

    def __le__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() <= other)
        else:
             return (self.ufloat() <= other.ufloat())

    def __gt__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() > other)
        else:
             return (self.ufloat() > other.ufloat())

    def __ge__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() >= other)
        else:
             return (self.ufloat() >= other.ufloat())

    def __eq__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() == other)
        else:
             return (self.ufloat() == other.ufloat())

    def __ne__(self, other):
        if(other.__class__.__name__ != "Quantity"):
            return (self.ufloat() != other)
        else:
             return (self.ufloat() != other.ufloat())



    def __str__(self):
        return ("" if self.operator == Operator.eq else self.operator) +  " " + str(self.ufloat())


class Ndm_base():
    """Base class of the Nuclar Data Model

    Attributes:
       _csv_title (str): the title of the csv representation of this class

    """
    _csv_title = '' 

    def __init__(self):
        self.myfilter = ''
        self.pk = ''

    def _populate(self,data):
        """ takes a json structure and populates the Quantities of this class, as well as the other variables 
        """
        pass

    def _join_filter(self,filter, fk_filter):
        """Joins the filter specified by the user with the foreign key to follow the link to another class.
        For example 
        if nuc = nuclide("135XE")
        nuc.levels("LEVEL.JP = '2+') has an explict filter for JP, but also an embedded foreign key to reach only 135XE

        Args:
            filter (str): the user-specified filter
            fk_filter (str): the foreign key to be added
        
        Returns:
            String: the joined flters
        """
        _filter = ""
        if(filter != ''):
            _filter = filter 

        if(_filter != ''  and self.myfilter != ''):
            _filter = filter + " AND " + self.myfilter 
        else:
            _filter = self.myfilter


        idx = _filter.find("ORDER")
        if(idx > 0):
            _filter = _filter[0 : idx]
        
        if(_filter != ''  and fk_filter != ''):
            _filter = _filter + " AND " + fk_filter
        else:
            _filter = fk_filter

        return _filter 
    
    def _check_filter(self,filter, prev_filter):
        """ to handle the case when a property was first called with a filter, then without

        Args:

            filter (str): the new filter (DEFAULT means no filter specified)
            prev_filter (str): the previous filter, if any

        Returns:

            str: the filter to be applied

        """
        # without a filter, and it is the first call
        if(filter == DEFAULT and prev_filter == None):
            filter = ''
        # without a filter, but previously a filter was set
        elif(filter == DEFAULT and prev_filter != None):
            filter = prev_filter
        return filter    


    def _property_filler(self, property_name, func_name, filter, fk_filter, skip_prev_filter=False):
        """intialises an instance variable, like :py:meth:`ndlab.Nuclide.levels` for a :py:class:`ndlab.Nuclide`

        It uses reflection, the name of the variable to be set, the name of the function that 
        does the actual retrieval of the data, and the filter to be applied.
        Lazy creation : returns the existig value if the property is already filled and the filter has not changed

        Args:
        
            property_name (str): name of the property to be intialised
            func_name (str): name of the function in this module that  performs the task
            filter (str): filter passed to the function by the user
            fk_filter (str): str: foreign key(s) to be appended to the filter
            skip_prev_filter (bool) : False , do not append the exisiting filter 

        Returns: 
        
        object: the instance variable intialised 


        """
        if(filter == DEFAULT): filter = ""
        
        # pointer to the property from its name
        property = getattr(self,property_name)
        # pointer to the previous filter from its name
        prev_filter = getattr(self,(property_name + "_filter"))
        # whether the filter has changed
        filter = filter if skip_prev_filter else   self._check_filter(filter, prev_filter)
        
        # lazy creator: only if not assigned yet, or if the filter has chenged
        if(property == None or prev_filter != filter ):
            # pointer to the function from its name
            function = getattr(this,func_name)
            # assign the result to the property
          
            #property = function(self._join_filter(filter, fk_filter))

            property = function(  filter + ("" if filter == "" else " AND ") + fk_filter)
    
            # attach property to the instance, otherwise it is local
            setattr(self, property_name, property)
            # set the new filter
            setattr(self, (property_name + "_filter"), filter)

        return property   


    def csv(self):
        """ Generates a String with the CSV representation for an instance of class

        the attribute _cst_title stores the first row of the csv with the field names

        Returns:
            string: the csv
        """
        sep = CSV_SEP
        ret = ""
        fields = self._csv_title.split(CSV_SEP)
        for field in fields:
           
            if(field.endswith("_unc")):
                continue

            attr = getattr(self, field, "stop") 
           
            if(attr != "stop"):                  
                if(isinstance( attr, Quantity)):
                    ret += sep + attr.csv()
                else:
                    ret += sep + str(attr)
            else:  
                pass
                # print("null " ,field, attr)     
         
        return  ret[1:]


class Nuclide(Ndm_base):
    """The properties of given Z and N pair
    
    Note that properties like Half-life, etc are to be accessed through its ground state (gs)

    :ivar int z: number of protons
    :ivar int n: number of neutrons
    :ivar str nucid: nuclide id mass + element symbol 135XE
    :ivar Quantity charge_radius: charge radius
    :ivar Quantity atomic_mass: atomic mass
    :ivar Quantity mass_excess: mass excess
    :ivar Quantity binding_en: binding en
    :ivar Quantity beta_decay_en: beta decay energy
    
    :ivar Quantity s2n: 2-neutron separation energy
    :ivar Quantity s2p: 2-protons separation energy
    :ivar Quantity qa: Q-value for alpha decay
    :ivar Quantity abundance: natural abundance in mole fraction
    :ivar Level gs: ground state
    :ivar Nuclide[] daughters: direct daughters of the nuclide, including excited states decays
    :ivar Nuclide[] parents: parents of the nuclide
    :ivar Nuclide[] daughters_chain: all possible offsprings of the nuclide
    :ivar Nuclide[] parents_chain: all possible ancestors of the nuclide
    :ivar Decay[] decays: all decays, including fron metastable states, for which decay radiations are given
    """

    _csv_title = "z,n,nucid,elem_symbol,charge_radius,charge_radius_unc,charge_radius_limit,atomic_mass,atomic_mass_unc,atomic_mass_limit,mass_excess,mass_excess_unc,mass_excess_limit,binding_en,binding_en_unc,binding_en_limit,qbm,qbm_unc,qbm_limit,qa,qa_unc,qa_limit,qec,qec_unc,qec_limit,sn,sn_unc,sn_limit,sp,sp_unc,sp_limit,qbmn,qbmn_unc,qbmn_limit,abundance,abundance_unc,abundance_limit"

    def __init__(self):
        super().__init__()
        self.z = None
        self.n = None
        self.nucid = None
        self.elem_symbol = None
        self.charge_radius = Quantity("charge_radius")
        self.atomic_mass = Quantity("atomic_mass")
        self.mass_excess = Quantity("mass_excess")
        self.binding_en = Quantity("binding_en")
        self.qbm = Quantity("beta_decay_en")
        self.s2n = Quantity("s2n")
        self.s2p = Quantity("s2p")
        self.qa = Quantity("qa")
        self.qbmn = Quantity("qbmn")
        self.sn = Quantity("sn")
        self.sp = Quantity("sp")
        self.qec = Quantity("qec")
        self.abundance = Quantity("abundance")
      
        self._levels = None
        self._levels_filter = None

        self._gammas = None
        self._gammas_filter = None

        self._dr_photons = None
        self._dr_photons_filter = None

        self._daughters = None
        self._parents = None

        self._decays = None

    def _populate(self,data):
        self.z =  _int_check(data["z"])
        self.n =  _int_check(data["n"])
        self.nucid =  data["nucid"]
        self.elem_symbol =  data["elem_symbol"]
        self.charge_radius._populate(data)
        self.atomic_mass._populate(data)
        self.mass_excess._populate(data)
        self.binding_en._populate(data)
        self.qbm._populate(data)
        self.s2n._populate(data)
        self.s2p._populate(data)
        self.qa._populate(data)
        self.qbmn._populate(data)
        self.sn._populate(data)
        self.sp._populate(data)
        self.qec._populate(data)
        self.abundance._populate(data)# =  _float_check(data["abundance"])

        self.pk = self.nucid

    def levels(self, filter=DEFAULT):
        """Energy levels of this nuclide

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`NUCLIDE <NUCLIDE>` entity  
        Returns: 
           the  list of :py:class:`ndlab.Level` of this nuclide
        """
       
        return self._property_filler("_levels","levels", filter, "  LEVEL.NUC_ID = '" + self.nucid + "' ORDER BY LEVEL.SEQNO"  )
    

    def gammas(self, filter=DEFAULT):
        """Gamma transitions between levels of this nuclide

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`NUCLIDE <NUCLIDE>` entity
        Returns: 
           the  list of :py:class:`ndlab.Gamma` of this nuclide
        """

        return self._property_filler("_gammas","gammas", filter, "  GAMMA.NUC_ID = '" + self.nucid + "' ORDER BY GAMMA.START_LEVEL_SEQNO , GAMMA.SEQNO" , True)
    
    @property
    def daughters(self):
       
        if(self._daughters == None):
            self._daughters = this._generator("L_DECAY.DAUGHTER.ALL", "Nuclide", "L_DECAY.NUC_ID = '" + self.nucid + "' " )
        return self._daughters
    
    @property
    def parents(self):

        if(self._parents == None):
            self._parents = this._generator("L_DECAY.NUC.ALL", "Nuclide", "L_DECAY.DAUGHTER_NUC_ID = '" + self.nucid + "' " )
        return self._parents

    @property
    def decays(self):
        if(self._decays == None):
            self._decays = this._generator("L_DECAY.ALL", "L_decay", " L_DECAY.NUC_ID = '" + self.nucid + "' ORDER BY L_DECAY.LEVEL_SEQNO , L_DECAY.MODE" ) #_DR_BASE.PARENT_NUC_ID = L_DECAY.NUC_ID and
        return self._decays
       
    @property
    def gs(self):
        return self.levels( " LEVEL.SEQNO = 0 ")[0]

    @property
    def daughters_chain(self):
        offs =[]    
        dau_ids = self._offsprings(self)
        for nid in dau_ids:
            offs.append(nuclide(nid))
        
        return offs

    @property
    def parents_chain(self):
        pars =[]
        par_ids = self._ancestors(self)
        for nid in par_ids:
            pars.append(nuclide(nid))
        
        return pars


    def _offsprings(self, nuc, offsprings = []):
       
        _daugs = nuc.daughters # direct daughters

        go = False # turns true when anything new is added
        for d in _daugs: # loop on direct daughters
            if not d.nucid in offsprings: # if not already added, add to the list
                offsprings.append(d.nucid)
                go = True  # nuclide added, need to call again
            
        if(not go): return offsprings # nothing added, stop here
        # after the first call of daughter_chain, when called again the offstring param still has the previous value - why ? 
    
        for d in _daugs: 
            self._offsprings(d, offsprings)
        
        return offsprings

    def _ancestors(self, nuc, allpars = []):  
        _pars = nuc.parents 
        go = False # if anythinks new is added
        for d in _pars:
            if not d.nucid in allpars:
                allpars.append(d.nucid)
                go = True
            
        if(not go): return allpars
    
        for d in _pars:
            self._ancestors(d, allpars)
        
        return allpars


class Level(Ndm_base):
    """Properties of an energy eigenstate of a Nuclide

     z, n, and nucid are for convenience. The can be accessed also through the 'nuclide' property

     :ivar int z: number of protons of the nuclide
     :ivar int n: number of neutron of the nuclide
     :ivar string nucid: nuclide's indentifier, e.g. 135XE
     :ivar int l_seqno: sequential number or the level, 0 being the g.s.
     :ivar Quantity energy: energy in keV
     :ivar Quantity half_life: H-l in the units given by the evaluation
     :ivar string half_life_units: units given by the evaluation
     :ivar Quantity half_life_sec: H-l given in seconds
     :ivar string jp_str: Jp given in the evaluation
     :ivar int jp_order: occurrence of this Jp value, 0 being the one closest to the g.s.
     :ivar float j: Angular momentum assignment given by :ref:`RIPL <jp-label>`
     :ivar int parity: parity assignment given by :ref:`RIPL <jp-label>`
     :ivar string jp_method: method of jp assignment by :ref:`RIPL <jp-label>`
     :ivar Quantity quadrupole_em: Quadrupole electric moment in barn
     :ivar Quantity dipole_mm: Dipole magnetic moment in nuclear magnetons
     :ivar string questionable: whether the existence  is questionable
     :ivar string configuration: nuclear configuration 
     :ivar string isospin: isospin
     :ivar Nuclide nuclide: access to the nuclide
     :ivar Nuclide[] daughters: the direct daughters of the level decay, if any

    """

    _csv_title = "z,n,nucid,l_seqno,energy,energy_unc,energy_limit,half_life,half_life_unc,half_life_limit,half_life_units,half_life_sec,half_life_sec_unc,half_life_sec_limit,j,parity,jp_order,jp_method,jp_str,quadrupole_em,quadrupole_em_unc,quadrupole_em_limit,dipole_mm,dipole_mm_unc,dipole_mm_limit,questionable,configuration,isospin"

    def __init__(self):
        super().__init__()
        self.z = None
        self.n = None
        self.nucid = None
        self.l_seqno = None
        self.energy = Quantity("energy")
        self.half_life = Quantity("half_life")
        self.half_life_units = None
        self.half_life_sec = Quantity("half_life_sec")
        self.j = None
        self.jp_str = None
        self.parity = None
        self.jp_order = None
        self.jp_method = None
        self.quadrupole_em = Quantity("quadrupole_em")
        self.dipole_mm = Quantity("dipole_mm")
       
        self.questionable = None
        self.configuration = None
        self.isospin = None
       
        self._nuclides = None
        self._daughters = None
        self._gammas = None
        self._gammas_filter = None
        self._l_decays = None
        self._l_decays_filter = None
       


    def _populate(self,data):
        self.z =  _int_check(data["z"])
        self.n =  _int_check(data["n"])
        self.nucid =  data["nucid"]        
        self.l_seqno =  _int_check(data["l_seqno"])
        self.energy._populate(data)
        self.half_life._populate(data)
        self.half_life_units =  data["half_life_units"]
        self.half_life_sec._populate(data) 
        self.jp_str =  _str_check(data["jp_str"])
        self.j =  _str_check(data["j"])
        self.parity =  _int_check(data["parity"])
        self.jp_order =  _int_check(data["jp_order"])
        self.jp_method =  _int_check(data["jp_method"])
        self.quadrupole_em._populate(data)
        self.dipole_mm._populate(data)
       
        self.questionable =  _str_check(data["questionable"])
        self.configuration = _str_check( data["configuration"])
        self.isospin = _str_check( data["isospin"])

        self.pk = self.nucid + '-' + str(self.l_seqno)

    @property
    def nuclide(self):
        if(self._nuclides == None):
            self._nuclides =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.nucid + "' ")  
        return self._nuclides[0]

    @property
    def daughters(self):
        if(self._daughters):
            return self._daughters

        self._daughters = []
        for d in self.decays():
            self._daughters.append(d.daughter)
        return  self._daughters 


    def gammas(self, filter=DEFAULT):
        """Gamma transitions starting from this level

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`LEVEL <LEVEL>` entity
        Returns: 
           the  list of :py:class:`ndlab.Gamma` starting from this level
        """

        return self._property_filler("_gammas","gammas", filter, " GAMMA.NUC_ID = '" + self.nucid + "' and GAMMA.START_LEVEL_SEQNO = " + str(self.l_seqno) + " ORDER BY GAMMA.SEQNO")
        
    def decays(self, filter=DEFAULT):
        """Decay modes of this level

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`NUCLIDE <NUCLIDE>` entity
        Returns: 
           the  list of :py:class:`ndlab.L_decays` of this level
        """

        return self._property_filler("_l_decays","l_decays", filter, " L_DECAY.NUC_ID = '" + self.nucid + "' and L_DECAY.LEVEL_SEQNO = " + str(self.l_seqno), True )


class L_decay(Ndm_base): 
    """Decay process

    Description of a level decay: parent, daughter, radiations, etc...
    nucid , l_seqno, and daughter_nucid are for convenience. The can be accessed also through the 'nuclide', 'daughter', and 'level' properties, respectively


    :ivar string nucid: decaying nuclide indentifier, e.g. 135XE
    :ivar int l_seqno: sequential number or the decaying level, 0 being the g.s.
    :ivar string daughter_nucid: daughter nuclide indentifier, e.g. 135XE
    :ivar Quantity perc: decays per 100 decay of the parent
    :ivar Nuclide nuclide: the parent nuclide
    :ivar Level level: the parent level
    :ivar Nuclide[] daughters: the direct daughters of the  decay
    :ivar Nuclide nuclide: the parent nuclide
    :ivar Decay_mode mode: the decay mode
    :ivar Quantity toten_recoil: total recoil energy [keV]
    :ivar Quantity q_togs: Q-value  [keV]

    """
    _csv_title = "z,n,nucid,l_seqno,code,daughter_nucid,z_dau,n_dau,perc,perc_unc,perc_limit,q_togs,q_togs_unc,q_togs_limit"

    def __init__(self):
        super().__init__()

        self.nucid = None
        self.l_seqno = None
        self.code = None
        self.daughter_nucid = None

        self.perc = Quantity("perc")
        self._en_recoil = Quantity("recoil_tot_en")
        self.q_togs = Quantity("q_togs")
        
        self._gamma = None
        self._gamma_filter = None
        self._alpha = None
        self._alpha_filter = None
        self._annihil = None
        self._annihil_filter = None
        self._betam = None
        self._betam_filter = None
        self._anti_nu = None
        self._anti_nu_filter = None
        self._betap = None
        self._betap_filter = None
        self._annhils = None
        self._annhils_filter = None
        self._nu = None
        self._nu_filter = None
        self._x = None
        self._x_filter = None
        self._ce = None
        self._ce_filter = None
        self._auger = None
        self._auger_filter = None
        self._photon_tot = None 
        self._photon_tot_filter = None

        self._nuclide = None
        self._levels = None
        self._daughter = None
        self._mode = None

    def _populate(self,data):
       
        self.z =  _int_check(data["z"])
        self.n =  _int_check(data["n"])
        self.nucid =  data["nucid"]
        self.l_seqno =  _int_check(data["l_seqno"])
        self.code =  _int_check(data["decay_code"])
        self.daughter_nucid =  data["daughter_nucid"]
        self.z_dau =  _int_check(data["z_dau"])
        self.n_dau =  _int_check(data["n_dau"])
        self.perc._populate(data)
        self._en_recoil._populate(data)
        self.q_togs._populate(data)
   
        self.pk = self.nucid + '-' + str(self.l_seqno) + '-' + str(self.code)


        self._sql_decrad =  " _DR_BASE.PARENT_NUC_ID = '" + self.nucid + "' and _DR_BASE.PARENT_LEVEL_SEQNO = " + str(self.l_seqno) + " and _DR_BASE.MODE = " + str(self.code) + " ORDER BY _DR_BASE.ENERGY"

    def gammas(self, filter=DEFAULT):
        """Gamma radiation from this decay

        The radiation is emitted by the daughter

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_GAMMA <DR_GAMMA>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_gamma` from this decay
        """

        return self._property_filler("_gamma","dr_gammas", filter, " DR_GAMMA.PARENT_NUC_ID = '" + self.nucid + "' and DR_GAMMA.PARENT_LEVEL_SEQNO = " + str(self.l_seqno) + " and DR_GAMMA.MODE = " + str(self.code) + " ORDER BY DR_GAMMA.SEQNO") 

    def alphas(self, filter=DEFAULT):
        """Alpha radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_ALPHA <DR_ALPHA>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_alpha` from this decay
        """
        return self._property_filler("_alpha","dr_alphas", filter, self._sql_decrad )
    
    def annihil(self, filter=DEFAULT):
        """Annihilation radiation

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_ANNIHIL <DR_ANNIHIL>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_annihil` from this decay
        """
        return self._property_filler("_annihil","dr_annihil", filter, self._sql_decrad )

    def betas_m(self, filter=DEFAULT):
        """Beta- radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_BETAM <DR_BETAM>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_betam` from this decay
        """
        
        return self._property_filler("_betam","dr_beta_ms", filter, self._sql_decrad )

    def anti_nus(self, filter=DEFAULT):
        """Anti neutrino radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_ANTI_NU <DR_ANTI_NU>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_anti_nu` from this decay
        """
        
        return self._property_filler("_anti_nu","dr_anti_nus", filter, self._sql_decrad )

    def nus(self, filter=DEFAULT):
        """Neutrino radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_NU <DR_NU>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_Nu` from this decay
        """
        dm = self._property_filler("_nu","dr_nus", filter, self._sql_decrad )   
        ddm = copy.deepcopy(dm) 
        for d in dm:
            dd = copy.deepcopy(d)
            dd.energy = d.energy_ec
            dd.intensity = d.intensity_ec
            ddm.append(dd)
        self._nu = ddm
        return self._nu

    def betas_p(self, filter=DEFAULT):
        """Beta+ radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_BETAP <DR_BETAP>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_betap` from this decay
        """
        return self._property_filler("_betap","dr_beta_ps", filter, self._sql_decrad )  

    def annihil(self, filter=DEFAULT):
        """Annihilation radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_ANNIHIL <DR_ANNIHIL>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_annihil` from this decay
        """
        
        return self._property_filler("_annhils","dr_annihil", filter, self._sql_decrad ) 

    def dr_photon_tot(self, filter=DEFAULT):
        """Photons emitted in the decay process, if any, regardless of the daughter or the radiation type (X- or Gamma- ray)

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_PHOTON_TOTAL <DR_PHOTON_TOTAL>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_photon_tot` from this decay

        """
        
        return self._property_filler("_photon_tot","dr_photon_tot", filter, "  DR_PHOTON_TOTAL.PARENT_NUC_ID = '" + self.nucid + "' and DR_PHOTON_TOTAL.PARENT_LEVEL.SEQNO = " + str(self.l_seqno) + " ORDER BY DR_PHOTON_TOTAL.ENERGY" , True ) 

    @property
    def nuclide(self):
         if(self._nuclide == None):
             self._nuclide = this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.nucid + "' " )
             if(self._nuclide != None and len(self._nuclide) > 0):
                self._nuclide = self._nuclide[0]
         return self._nuclide  
    
    @property
    def level(self):
         if(self._levels == None):
             self._levels = this._generator("LEVEL", "Levels",  " LEVEL.NUC_ID = '" + self.nucid + "' and LEVEL.SEQNO = " + self.l_seqno)
         return self._levels  

    @property
    def daughter(self):
         if(self._daughters == None):
             self._daughters = this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.daughter_nucid + "' ")
         return self._daughters[0]  

    @property
    def mode(self):
         if(self._mode == None):
            self._mode =  this._generator("DECAY_MODE","Decay_mode" " DECAY_MODE.DECAY_CODE = '" + str(self.code) + "' ")
         return self._mode[0].dataset_code

    @property
    def toten_recoil(self):
        return self._en_recoil


    def xs(self, filter=DEFAULT):
        """X-rays radiation from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_X <DR_X>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_x` from this decay
        """

        return self._property_filler("_x","dr_xs", filter, self._sql_decrad )  

    def convels(self, filter=DEFAULT):
        """Conversion electrons from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_CONV_EL <DR_CONV_EL>` entity
        Returns: 
           the  list of :py:class:`ndlab.dr_conv_el` from this decay
        """

        return self._property_filler("_ce","dr_convels", filter, self._sql_decrad )  
        
    def augers(self, filter=DEFAULT):
        """Auger electrons from this decay

        Args:
            filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_AUGER <DR_AUGER>` entity
        Returns: 
           the  list of :py:class:`ndlab.Dr_auger` from this decay
        """

        return self._property_filler("_auger","dr_augers", filter, self._sql_decrad )          

    def tot_rad_en(self, radiations):
        """ Energy emitted by a set of radiations

        calculated as energy * intensity / 100

        Args:
            radiations (Decay_radiation): list of any decay radiations
        
        Returns:
            Quantity: the energy
        """
        if(radiations == None or len(radiations)==0):
             return ufloat(0,0);
        return sum([radiations[i].energy * radiations[i].intensity for i in range(len(radiations))])/100
    
    def tot_measured_en(self):
        """ Total energy emitted per 100 decays of the parent

        calculated as sum (energy * intensity / 100 ) * Q_togs over all radiations

        Returns:
            Quantity: the total energy
        """

        rads = [self.xs(), self.gammas(), self.convels(), self.augers(), self.alphas(), self.betas_m(), self.betas_p(), self.nus(), self.anti_nus(), self.annihil()]
        sm = []
        for r in rads:
            sm.append(self.tot_rad_en(r))
        sm.append(self.toten_recoil)
        return sum(sm)*self.q_togs   


class Gamma(Ndm_base):
    """Electromagnetic transition between levels of the same nuclide

    z, n, and nucid can be accessed also through the 'nuclide' property. l_seqno can be accessed though the 'level' property

    :ivar int z: number of protons of the nuclide
    :ivar int n: number of neutron of the nuclide
    :ivar string nucid: nuclide's indentifier, e.g. 135XE
    :ivar int l_seqno: sequential number of the start level, 0 being the g.s.
    :ivar int g_seqno: sequential number of this gamma within the start level gammas, 0 being the lowest energy one
    :ivar Nuclide nuclide: the  nuclide
    :ivar Level start_level: the start level
    :ivar Level end_level: the start level
    :ivar Quantity energy: energy [keV]
    :ivar Quantity rel_photon_intens: relative photon intensity %
    :ivar string multipolarity: multipolarity
    :ivar Quantity mixing_ratio: mixing ratio 
    :ivar Quantity tot_conv_coeff: total conversion coefficient
    :ivar Quantity bew: reduced electric transition probabilities in Weisskopf units    
    :ivar Quantity bew_order: bew order
    :ivar Quantity bmw: reduced magnetic transition probabilities in Weisskopf units   
    :ivar Quantity bmw_order: bmx order
    :ivar string questionable: whether the existence  is questionable

    """
    _csv_title = 'z,n,nucid,g_seqno,l_seqno,energy,energy_unc,energy_limit,rel_photon_intens,rel_photon_intens_unc,rel_photon_intens_limit,multipolarity,mixing_ratio,mixing_ratio_unc,mixing_ratio_limit,tot_conv_coeff,tot_conv_coeff_unc,tot_conv_coeff_limit,bew,bew_unc,bew_limit,bew_order,bmw,bmw_unc,bmw_limit,bmw_order,questionable,final_l_seqno'
    
    def __init__(self):
        super().__init__()
        self.z = None
        self.n = None
        self.nucid = None
        self.g_seqno = None
        self.l_seqno = None
        self.energy = Quantity("energy")
        self.rel_photon_intens = Quantity("rel_photon_intens")
        self.multipolarity = None
        self.mixing_ratio = Quantity("mixing_ratio")
        self.tot_conv_coeff = Quantity("tot_conv_coeff")
        self.bew = Quantity("bew") 
        self.bew_order = None
        self.bmw = Quantity("bmw")
        self.bmw_order = None
        self.questionable = None
        self.final_l_seqno = None

        self._nuclides = None
        self._start_level = None
        self._end_level = None

    @property
    def nuclide(self):
        if(self._nuclides == None):
            self._nuclides =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.nucid + "' ")  
        return self._nuclides[0]

    @property
    def start_level(self):
         if(self._start_level == None):
             self._start_level = this._generator("LEVEL", "Level",  " LEVEL.NUC_ID = '" + self.nucid + "' and LEVEL.SEQNO = " + str(self.l_seqno))
         return self._start_level  

    @property
    def end_level(self):
            if(self._end_level == None):
                self._end_level = this._generator("LEVEL", "Level",  " LEVEL.NUC_ID = '" + self.nucid + "' and LEVEL.SEQNO = " + str(self.final_l_seqno))
                if(self._end_level != None): self._end_level = self._end_level[0]

            return self._end_level


    def _populate(self,data):
        self.z =  _int_check(data["z"])
        self.n =  _int_check(data["n"])
        self.nucid =  data["nucid"]
        self.g_seqno =  _int_check(data["g_seqno"])
        self.l_seqno =  _int_check(data["l_seqno"])
        self.energy._populate(data)
        self.rel_photon_intens._populate(data)
        self.multipolarity =  _str_check(data["multipolarity"])
        self.mixing_ratio._populate(data)
        self.tot_conv_coeff._populate(data)
        self.bew._populate(data)
        self.bew_order =  _int_check(data["bew_order"])
        self.bmw._populate(data)
        self.bmw_order =  _int_check(data["bmw_order"])
        self.questionable =  _str_check(data["questionable"])
        self.final_l_seqno = _int_check(data["final_l_seqno"])

        self.pk = self.nucid + '-' + str(self.l_seqno) + '-' + str(self.g_seqno)




class Decay_radiation(Ndm_base):
    """Base class for decay radiations

    Its Attributes are inherited by all the Dr_* classes describing each type of radiation

    parent_nucid , parent_l_seqno, daughter_nucid, and daughter_l_seqno are for convenience. The can be accessed also through the 'nuclide', 'daughter', and 'level' properties, respectively


    :ivar string parent_nucid: parent nuclide indentifier, e.g. 135XE
    :ivar int parent_l_seqno: sequential number or the parent level, 0 being the g.s.
    :ivar string daughter_nucid: daughter nuclide indentifier, e.g. 135XE

    :ivar Nuclide parent: the  parent nuclide
    :ivar Level daughter: the daughter nuclide
    :ivar Level fed_level: the daughter level populated by the decay
    :ivar L_decay decay: access to the level decay, with all the other radiations emitted 
   
    """

    _csv_title = 'parent_nucid,parent_l_seqno,parent_z,parent_n,daughter_nucid,daughter_z,daughter_n,daughter_l_seqno,adopted_daughter_g_seqno,decay_code,type_a,type_b,type_c,ec_energy,ec_energy_unc,ec_energy_limit,bpec_intensity,bpec_intensity_unc,bpec_intensity_limit,ec_intensity,ec_intensity_unc,ec_intensity_limit,b_logft,b_logft_unc,b_logft_limit,intensity,intensity_unc,intensity_limit,b_trans_type,energy,energy_unc,energy_limit,a_hindrance,a_hindrance_unc,a_hindrance_limit,b_endpoint,b_endpoint_unc,b_endpoint_limit,d_energy_x,d_energy_x_unc,d_energy_x_limit,r_seqno,energy_nu,energy_nu_unc,energy_nu_limit'
    _csv_title_short = 'parent_nucid,parent_l_seqno,parent_z,parent_n,daughter_nucid,daughter_z,daughter_n,daughter_l_seqno,energy,energy_unc,energy_limit,intensity,intensity_unc,intensity_limit'
  
#    adopted_daughter_g_seqno,decay_code,type_a,type_b,type_c,ec_energy,ec_energy_unc,ec_energy_limit,bpec_intensity,bpec_intensity_unc,bpec_intensity_limit,ec_intensity,ec_intensity_unc,ec_intensity_limit,b_logft,b_logft_unc,b_logft_limit,intensity,intensity_unc,intensity_limit,b_trans_type,energy,energy_unc,energy_limit,a_hindrance,a_hindrance_unc,a_hindrance_limit,b_endpoint,b_endpoint_unc,b_endpoint_limit,d_energy_x,d_energy_x_unc,d_energy_x_limit,r_seqno,energy_nu,energy_nu_unc,energy_nu_limit'

    def __init__(self):
        super().__init__()
        self.parent_nucid = None
        self.parent_l_seqno = None
        self.daughter_nucid = None
        self.daughter_l_seqno = None

        self.decay_code = None
        self.type_a = None
        self.type_b = None
        self.type_c = None

        self.intensity = Quantity("intensity")
        self.energy = Quantity("energy")

        self.r_seqno = None

        self._parent = None
        self._daughter = None
        self._fed_level = None
        self._start_level = None
        self._decay = None


    def _populate(self,data):
        self.parent_nucid =  data["parent_nucid"]
        self.parent_l_seqno =  _int_check(data["parent_l_seqno"])
        self.parent_z =  _int_check(data["z"])
        self.parent_n =  _int_check(data["n"])

        self.daughter_nucid =  data["daughter_nucid"]
        self.daughter_l_seqno =  _int_check(data["adopted_daughter_l_seqno"])
        self.daughter_z = _int_check(data["z_dau"])
        self.daughter_n = _int_check( data["n_dau"])


        self.decay_code =  _int_check(data["decay_code"])
        self.type_a =  data["type_a"]
        self.type_b =  data["type_b"]
        self.type_c =  data["type_c"]
        self.intensity._populate(data)
        self.energy._populate(data)
        self.r_seqno =  _int_check(data["r_seqno"])

        self.pk = str(self.r_seqno)


    @property
    def parent(self):
        if(self._parent == None):
                self._parent =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.parent_nucid + "' ")  
        return self._parent[0]

    @property
    def daughter(self):
        if(self._daughter == None):
                self._daughter =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.daughter_nucid + "' ")  
        return self._daughter[0]

    @property
    def fed_level(self):
        if(self._fed_level == None):
            self._fed_level = this._generator("LEVEL", "Level",   " LEVEL.NUC = '" + self.daughter_nucid + "' and LEVEL.SEQNO = " + str(self.daughter_l_seqno)  + " ")
        return self._fed_level[0]  

    @property
    def parent_level(self):
        if(self._parent_level == None):
            self._parent_level = this._generator("LEVEL", "Level",   " LEVEL.NUC = '" + self.parent_nucid + "' and LEVEL.SEQNO = " + str(self.parent_l_seqno)  + " ")
        return self._parent_level[0]  

    @property
    def decay(self):
        if(self._decay == None):
            self._decay = this._generator("L_DECAY","L_decay", " L_DECAY.NUC = '" + self.parent_nucid + "' and L_DECAY.LEVEL = " + str(self.parent_l_seqno)  + " and L_DECAY.CODE = " +str(self.decay_code) + " ")
        return self._decay[0]


class Decay_mode(Ndm_base):
  
    def __init__(self):
        super().__init__()
        self.ensdf_code = None
        self.decay_code = None
        self.dataset_code = None


    def _populate(self,data):
        self.ensdf_code =  data["ensdf_code"]
        self.decay_code =  _int_check(data["decay_code"])
        self.dataset_code =  data["dataset_code"]

        self.pk = str(self.decay_code)




class _Fy(Ndm_base):
    """Base class for Fission yields

    :ivar Nuclide parent: the fissioning nuclide
    :ivar Nuclide daughter: the product nuclide
    :ivar Quantity thermal: thermal neutron fission yield
    :ivar Quantity fast: fast neutron fission yield
    :ivar Quantity mev_14: 14 MeV neutron fission yield


    """
    _csv_title = "parent_nucid,daughter_nucid,l_seqno,thermal,thermal_unc,thermal_limit,fast,fast_unc,fast_limit,mev_14,mev_14_unc,mev_14_limit"

    def __init__(self):
        super().__init__()
        self.parent_nucid = None
        self.daughter_nucid = None
        self.l_seqno = None

        self.thermal = Quantity('ther_yield')
        self.fast = Quantity('fast_yield')
        self.mev_14 = Quantity('mev_14_yield')

        self._parent = None
        self._daughter = None


    def _populate(self,data):
        self.parent_nucid =  data["parent_nucid"]
        self.daughter_nucid =  data["daughter_nucid"]
        self.l_seqno =  _int_check(data["l_seqno"])
        self.thermal._populate(data)
        self.fast._populate(data)
        self.mev_14._populate(data)

        self.pk = self.parent_nucid + '-' + self.daughter_nucid + '-' + str(self.l_seqno)
    
    @property
    def parent(self):
        if(self._parent == None):
                self._parent =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.parent_nucid + "' ")  
        return self._parent[0]
    @property
    def daughter(self):
        if(self._daughter == None):
                self._daughter =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.daughter_nucid + "' ")  
        return self._daughter[0]

class Cum_fy(_Fy):
    """Cumulative fission yield

    :ivar Nuclide parent: the fissioning nuclide
    :ivar Nuclide daughter: the product nuclide
    :ivar Quantity thermal: thermal neutron fission yield
    :ivar Quantity fast: fast neutron fission yield
    :ivar Quantity mev_14: 14 MeV neutron fission yield
    """
    
    def __init__(self):
        super().__init__()
    
    def _populate(self,data):
        super()._populate(data)


class Ind_fy(_Fy):
    """Independent fission yield

    :ivar Nuclide parent: the fissioning nuclide
    :ivar Nuclide daughter: the product nuclide
    :ivar Quantity thermal: thermal neutron fission yield
    :ivar Quantity fast: fast neutron fission yield
    :ivar Quantity mev_14: 14 MeV neutron fission yield
    """

    
    def __init__(self):
        super().__init__()
    
    def _populate(self,data):
        super()._populate(data)



class Dr_alpha(Decay_radiation):
    """Alpha decay radiation

    Inherits all the attributes of :py:class:`Decay_radiation`

    :ivar Quantity hindrance: hindrance factor

    """
    _csv_title = Decay_radiation._csv_title_short + ",hindrance,hindrance_unc,hindrance_limit"
    def __init__(self):
        super().__init__()

        self.hindrance = Quantity("a_hindrance")
       

    def _populate(self,data):
        super()._populate(data)
        self.hindrance._populate(data)


class Dr_betam(Decay_radiation):
    """Beta- decay radiation

    Inherits all the attributes of :py:class:`Decay_radiation`

    :ivar Quantity logft: Log ft
    :ivar Quantity endpoint: end point energy [keV]
    :ivar String trans_type: transition type

    """
    _csv_title = Decay_radiation._csv_title_short +   ',logft,logft_unc,logft_limit,trans_type,endpoint,endpoint_unc,endpoint_limit,anti_nu_energy,anti_nu_energy_unc,anti_nu_energy_limit'


    def __init__(self):
        super().__init__()

        self.logft = Quantity("logft")  
        self.trans_type = None
        self.endpoint = Quantity("b_endpoint")
        self.anti_nu_energy = Quantity("energy_nu")
      

    def _populate(self,data):
        super()._populate(data)
        self.logft._populate(data)
        self.trans_type =  _str_check(data["b_trans_type"])
        self.endpoint._populate(data)
        self.anti_nu_energy._populate(data)

class Dr_anti_nu(Decay_radiation):
    """Anti neutrino  decay radiation

    Inherits all the attributes of :py:class:`Decay_radiation`

    """

    def __init__(self):
        super().__init__()
        self.energy.name = "energy_nu"

    def _populate(self,data):
        super()._populate(data)

class Dr_nu(Decay_radiation):
    """Neutrino decay radiation

    Inherits all the attributes of :py:class:`Decay_radiation`

    """

    def __init__(self):
        super().__init__()
        self.intensity = Quantity("intensity")
        self.energy.name = "energy_nu"

        self.intensity_ec = Quantity("ec_intensity")
        self.energy_ec = Quantity("ec_energy")

    def _populate(self,data):
        super()._populate(data)
        self.intensity_ec._populate(data)
        self.energy_ec._populate(data)

class Dr_betap(Dr_betam):
    """Beta+/Electron Capture decay radiation

    Inherits all the attributes of :py:class:`Dr_betam`

    :ivar Quantity ec_energy: electron capture energy
    :ivar Quantity intensity: beta+ intensity
    :ivar Quantity ec_intensity: electron capture intensity
    :ivar Quantity bpec_intensity: beta+ + electron capture intensity

    """
    _csv_title = Decay_radiation._csv_title_short +   ',logft,logft_unc,logft_limit,trans_type,endpoint,endpoint_unc,endpoint_limit,nu_energy,nu_energy_unc,nu_energy_limit,ec_energy,ec_energy_unc,ec_energy_limit,bpec_intensity,bpec_intensity_unc,bpec_intensity_limit,ec_intensity,ec_intensity_unc,ec_intensity_limit'

    def __init__(self):
        super().__init__()

        self.ec_energy = Quantity("ec_energy")
        self.bpec_intensity = Quantity("bpec_intensity")
        self.ec_intensity = Quantity("ec_intensity")
        self.nu_energy = Quantity("energy_nu")

    def _populate(self,data):
        super()._populate(data)
        self.ec_energy._populate(data)
        self.bpec_intensity._populate(data)
        self.ec_intensity._populate(data)
        self.nu_energy._populate(data)


class Dr_delayed(Decay_radiation):
    """Delayed particle emission 

    Inherits all the attributes of :py:class:`Decay_radiation`

    :ivar Quantity energy_x: energy of the intermediate state
    :ivar string particle: delayed particle

    """

    _csv_title = Decay_radiation._csv_title_short +  ",particle,energy_x,energy_x_unc,energy_x_limit"


    def __init__(self):
        super().__init__()

        self.energy_x = Quantity("energy_x")
        self.particle = None


    def _populate(self,data):
        super()._populate(data)
        self.energy_x._populate(data)
        self.particle = self.type_a


class Dr_gamma(Gamma):
    """Gamma decay radiation

    Inherits all the attributes of :py:class:`Gamma`

    """

    _csv_title = 'z,n,nucid,g_seqno,l_seqno,energy,energy_unc,energy_limit,rel_photon_intens,rel_photon_intens_unc,rel_photon_intens_limit,multipolarity,mixing_ratio,mixing_ratio_unc,mixing_ratio_limit,tot_conv_coeff,tot_conv_coeff_unc,tot_conv_coeff_limit,bew,bew_unc,bew_limit,bew_order,bmw,bmw_unc,bmw_limit,bmw_order,questionable,final_l_seqno,parent_nucid,parent_l_seqno,decay_code,intensity,intensity_limit,intensity_unc'
  
    def __init__(self):
        super().__init__()
       
        self.decay_code = None
        self.intensity = Quantity("intensity")

        self._parent = []
        self._parent_level = []
        self._decay = []


    def _populate(self,data):
        super()._populate(data)
        self.parent_nucid =  data["parent_nucid"]
        self.parent_l_seqno =  _int_check(data["parent_l_seqno"])

        self.decay_code =  _int_check(data["decay_code"])
    
        self.intensity._populate(data)

    @property
    def parent(self):
        if(self._parent == None):
                self._parent =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.nucid + "' ")  
        return self._parent[0]

    @property
    def parent_level(self):
        if(self._parent_level == None):
            self._parent_level =  this._generator("LEVEL", "Levels", " LEVEL.NUC = '" + self.parent_nucid + "' and LEVEL.SEQNO = " + str(self.parent_l_seqno)  + " ", "levels")
        return self._parent_level[0]

    @property
    def decay(self):
        if(self._decay == None):
            self._decay = this._generator("L_DECAY","L_decays", " L_DECAY.NUC_ID = '" + self.parent_nucid + "' and L_DECAY.LEVEL_SEQNO = " + str(self.parent_l_seqno)  + " and L_DECAY.CODE = " +str(self.decay_code) + " ")
        return self._decay[0]

class Dr_photon_tot(Ndm_base):
    _csv_title = "parent_nucid,parent_l_seqno,energy,energy_unc,energy_limit,intensity,intensity_unc,intensity_limit,type,count"
   
    def __init__(self):
        self.parent_nucid = None
        self.parent_l_seqno = None
        self.energy = Quantity("energy")
        self.intensity = Quantity("intensity");
       
        self.count = 0
        self.type = None


    def _populate(self,data):
        self.parent_nucid =  data["parent_nucid"]
        self.parent_l_seqno = data["parent_l_seqno"]
        self.energy._populate(data)
        self.intensity._populate(data)
        
        self.type = data["type"]
        self.count = data["cnt"]

        self.pk =   self.parent_nucid  + '-' + str(self.parent_l_seqno)

    @property
    def parent(self):
        if(self._parent == None):
                self._parent =  this._generator("NUCLIDE", "Nuclide", " NUCLIDE.NUC_ID = '" + self.parent_nucid + "' ")  
        return self._parent[0]

 
    @property
    def parent_level(self):
        if(self._parent_level == None):
            self._parent_level = this._generator("LEVEL", "Level",   " LEVEL.NUC_ID = '" + self.parent_nucid + "' and LEVEL.SEQNO = " + str(self.parent_l_seqno)  + " ")
        return self._parent_level[0]  

class Dr_annihil(Decay_radiation):

    _csv_title = Decay_radiation._csv_title_short
    
    def __init__(self):
        super().__init__()

    def _populate(self,data):
        super()._populate(data)

class Dr_atomic(Ndm_base):
    _csv_title = "parent_nucid,parent_l_seqno,decay_code,intensity,intensity_unc,intensity_limit,energy,energy_unc,energy_limit,shell"
   
    def __init__(self):
        self.parent_nucid =  None
        self.parent_l_seqno =  None
        self.decay_code = None
        self.energy = Quantity("energy")
        self.intensity = Quantity("intensity");
        self.shell = None

    def _populate(self,data):

        self.parent_nucid =  data["parent_nucid"]
        self.parent_l_seqno =  _int_check(data["parent_l_seqno"])
        self.decay_code =  _int_check(data["decay_code"])
        self.intensity._populate(data)
        self.energy._populate(data)
        self.shell = data["type_c"]

        self.pk = str(data["r_seqno"])

class Dr_x(Dr_atomic):

    def __init__(self):
            super().__init__()
    def _populate(self,data):
            super()._populate(data)

class Dr_conv_el(Dr_atomic):

    def __init__(self):
            super().__init__()
    def _populate(self,data):
            super()._populate(data)

class Dr_auger(Dr_atomic):

    def __init__(self):
            super().__init__()
    def _populate(self,data):
            super()._populate(data)



def _generator(orm_table: str, nl_class_name: str , filter : str = ''):
    """ fills an array of ndlab classes by querying the database. 
    
    The 'populate' function of the ndlab entity performs the job, it makes use of reflection.
    The constructed query is a 'select * from tablename' + filter 

    Args:

        orm_table (str):   the name of the :py:mod:`ndlaborm` class for the query, e.g. 'NUCLIDE'
        nl_class_name (str): the name of the ndlab class that will be filled by the query result set, e.g. 'Nuclide'. 
                          The 'populate' function on the class links the result set with the class properties 
        filter (str) = '' : the filter to produce the where condition in the query 
    
    Returns:
 
        Object[]: list of  nl_class_name instances

    """

    # overwrite the filter
    _filter = this._filter if filter == ""  else filter

    #print("class ",nl_class_name, " filter ",filter, " _filter ", _filter, dblink.query_check(orm_table+".*",filter), "orm_table" , orm_table)
    
    if(not dblink.query_check(orm_table+".*",filter)):
        return ERROR_FILTER_NOT_VALID
    
    tablename = orm_table if orm_table.endswith("ALL") else orm_table + ".*"
    
    # call to the database
    jss = json.loads(json_data(tablename , _filter ))

    #print(" sql ", dblink.lastsql)
    #print(" json ", jss)
    #print("")
    # the return array
    objs = []

    # instanciate the factory
    classfact =  getattr(this, nl_class_name)

    # instanciate and fill the entities
    for js in jss:
        obj = classfact()
        # let the object remember its filter
        obj.myfilter = _filter
        obj._populate(js)
        objs.append(obj)

    return objs

def check_filter(filter, function):
    """Whether a filter is okay when applied to a given function

    Filter should query only one table (besides embedded foreign keys)

    Args:
        filter (str): the filter
        function (Function) : the ndlab function accepting the filter
    Returns:
        Boolean : 
     
    """
    table = function.__name__[:-1].upper() + ".*"
    return dblink.query_check(table,filter)

def nuclide(nucid):
    """A :py:class:`ndlab.Nuclide` from its identifyer
    
    Args:
        nucid (str): mass+element symbol, e.g.135XE
    Returns:
        Nuclide : the :ref:`NUCLIDE <NUCLIDE>` with this id
    """
    old_filter = this._filter
    this._filter = "NUCLIDE.NUC_ID = '" + nucid.upper()  + "'"
    nuc = nuclides()
    this._filter = old_filter
    if (nuc == None or len(nuc) == 0):
        return None

    return nuc[0]

def nuclides(filter = ""):
    """A list of :py:class:`ndlab.Nuclide`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`NUCLIDE <NUCLIDE>` entity  
    Returns:
        Nuclide : 
    """
    return _generator("NUCLIDE","Nuclide", filter)
   
def levels(filter = ""):
    """A list of :py:class:`ndlab.Level`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`LEVEL <LEVEL>` entity  
    Returns:
        Level : 
    """
    return _generator("LEVEL","Level", filter)

def gammas(filter = ""):
    """A list of :py:class:`ndlab.Gamma`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`GAMMA <GAMMA>` entity  
    Returns:
        Gamma : 
    """
    return _generator("GAMMA","Gamma", filter)

def l_decays(filter = ""):
    """A list of :py:class:`ndlab.L_decays`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`L_DECAY <L_DECAY>` entity  
    Returns:
        L_decay : 
    """
    return _generator("L_DECAY","L_decay", filter)

def decay_codes(filter = ""):
     return _generator("DECAY_CODE","Decay_code", filter)

def dr_alphas(filter = ""):
    """A list of :py:class:`ndlab.Dr_alpha`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_ALPHA <DR_ALPHA>` entity  
    Returns:
        Dr_alpha : 
    """

    return _generator("DR_ALPHA","Dr_alpha", filter)

def dr_gammas(filter = ""):
    """A list of :py:class:`ndlab.Dr_gamma`  
    
    Args:
       filter (str): :ref:`filter <filter-label>`  passed to the function by the user. It may contain only fields of the :ref:`DR_GAMMA <DR_GAMMA>` entity  
    Returns:
        Dr_gamma : 
    """

    return _generator("DR_GAMMA","Dr_gamma", filter)

def dr_annihil(filter = ""):
     return _generator("DR_ANNIHIL","Dr_annihil", filter) 

def dr_beta_ms(filter = ""):
     return _generator("DR_BETAM","Dr_betam", filter)

def dr_anti_nus(filter = ""):
     return _generator("DR_ANTI_NU","Dr_anti_nu", filter)

def dr_nus(filter = ""):
     return _generator("DR_NU","Dr_nu", filter)

def dr_beta_ps(filter = ""):
     return _generator("DR_BETAP","Dr_betap", filter)

def dr_xs(filter = ""):
     return _generator("DR_X","Dr_x", filter)

def dr_photon_tot(filter = ""):
     return _generator("DR_PHOTON_TOTAL","Dr_photon_tot", filter)     

def dr_convels(filter = ""):
     return _generator("DR_CONV_EL","Dr_conv_el", filter)

def dr_augers(filter = ""):
     return _generator("DR_AUGER","Dr_auger", filter)

def dr_delayeds(filter = ""):
     return _generator("DR_DELAYED","Dr_delayed", filter)

def cum_fys(filter = ""):
    return _generator("CUM_FY","Cum_fy", filter)

def ind_fys(filter = ""):
    return _generator("IND_FY","Ind_fy", filter)

def setfilter(where: str):
    ''' appendeds a filter to each query'''

    this._filter = where   

def remove_doublers(doublers):
    """ removes doublers from a list

    When one wants to be sure that each item is present only once

    Args:
        doublers (list): list of same-class items

    Returns:
        list: the list with only singlers  
    """
    if(len(doublers) == 0): return doublers

    singlers = []
    pks = []
    
    for n in doublers:
        if n.pk in pks: continue
        singlers.append(n)
        pks.append(n.pk)

    return singlers


def getfilter():
   return this._filter

def json_data(fields , filter ):
    """JSON data from a query

    Args:
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:

        str: JSON structure with the result set    
    """
    return _data_deliverer ('json', fields , filter )
# string    
def csv_data(fields , filter ):
    """CSV data from a query

    Args:
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:

        str: CSV structure with the data    
    """

    return _data_deliverer ('csv', fields , filter )
    
def _data_deliverer(return_type,fields , filter):
    """Delivers the data by querying the database

    It refers to dblink, the variable with an instance of ndlabdblink.DbLink class
    that handles the database

    It checks whether the db is local, or is remote and accessed through http

    Args:
        
        return_type (str): 'csv' or 'json' 
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:

        str: either a csv or a json structure with the data 

    """
    this.last_fields = fields
    this.last_filter = filter


    if(not dblink.query_check(fields,filter)):
        return ERROR_FILTER_NOT_VALID

    if(dblink.connected):
        return dblink.data_deliverer (return_type, fields , filter )
    else:
        return _httprequest(return_type,fields, filter).read().decode("utf8").strip()

# dblink
#def force_clean_query(force):
#    dblink.force_clean_query(force)

# dblink
#def lastquery_desc():
#    return dblink.query_desc(last_fields,last_filter)

def csv_nl(nl_items):
    """CSV from a list of :py:class:`ndlab.Ndm_base` classes

    for each instance, calls its csv() method and composes the overall result

    Args:

        nl_items (Object[]): list with ndlab class instances

    Returns:

        String: the CSV
    """
    if nl_items is None:
        return ""
    try:
        nl_items[0]
    except:
        return nl_items._csv_title + "\n" + nl_items.csv();
      
    return nl_items[0]._csv_title + "\n" + "".join([item.csv() + "\n" for item in nl_items] )

  
def pandas_csv_nl( nl_items):
    """Text stream with CSV from a list of :py:class:`ndlab.Ndm_base` classes

    Ready to be plugged into pandas. For each instance, calls its csv() method and composes the overall result

    Args:

        nl_items (Object[]): list with ndlab class instances

    Returns:

        StringIO: text stream  with the CSV
    """

    return  io.StringIO(csv_nl(nl_items))

def pandas_df_nl(list, pandas):
    """ Returns a Dataframe from a list of ndlab classes

    Args:
       list (List): list of ndlab class instances
        pandas (Object): the pandas module imported in the calling environment. E.g. pass when :code:`pd` when using :code:`import pandas as pd`

    Returns:
        Dataframe: the pandas dataframe

    """
    if(list == None or len(list) == 0):
         return None

    if (list.__class__.__name__ != 'str' and list[0].__module__ != 'ndlab'):
        return None

    # this is an error
    if(list.__class__.__name__ == 'str'):
        return pandas.read_csv(io.StringIO("MESSAGE\n"+list))


    return pandas.read_csv(pandas_csv_nl(list))
    

    

def pandas_df(fields, filter, pandas):
    """Creates a dataframe 
    
    If the database is local, calls pandas'  read_sql method using :py:class:`query_build` to build the query, and :py:class:`query_con`
    to get the db connection

    If the database is remote, calls the server API

    Args:
       fields (str): list of comma-separated :py:mod:`ndlaborm` fields
       filter (str): filter condition built with :py:mod:`ndlaborm` fields
       pandas (Object): the pandas module imported in the calling environment. E.g. pass when :code:`pd` when using :code:`import pandas as pd`

    Returns:
        Dataframe: the pandas dataframe

    """
    if(dblink.connected):
        try:
             return pandas.read_sql(query_build(fields, filter), query_con())
        except:
            try:
                # try to put blank spaces where needed
                force = dblink._sqlbuilder.force_clean 
                dblink.force_clean_query(True)
                qry = query_build(fields, filter)
                dblink.force_clean_query(force)
                return pandas.read_sql(qry, query_con())
            except:
                return None
    else:
        return pandas.read_csv(pandas_csv_web(fields, filter) )


def pandas_csv_web(fields, filter=""):
    """CSV data from the web server

    Ready to be plugged into pandas, accessing the database through http.
    To be used when the databse is not local, otherwise use :code:`pd.readsql(` :py:meth:`ndlab.query_build`, :py:meth:`ndlab.query_con`)

    Args:
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:

        http.client.HTTPResponse : the response to be read    
    """
    return _httprequest('csv',fields, filter) 

def query_con():
    """The connection to the database

    Returns:

      Connection: The connection to the database
    """
    return dblink._con_lite

def query_build(fields, filter=""):
    """The SQL query associated with fields and filter

    Args:
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:
        String : the SQL    

      
    """
    return dblink.query_build(fields, filter)

def _httprequest(return_type, fields, filter=""):
    """ Queries the database through http


    Args:
        return_type (str): 'csv' or 'json' 
        fields (str): list of comma-separated :py:mod:`ndlaborm` fields
        filter (str): filter condition built with :py:mod:`ndlaborm` fields

    Returns:

        http.client.HTTPResponse : the response to be read    
    """

    import urllib.request
    import urllib.parse

    url = "http://localhost:8123/cgi-bin/ndlab_server.py?" 
    #url =  "http://int-nds.iaea.org/cgi-bin/mvtest/ndlab_server.py?"
   
    query = "return_type=" + return_type + "&fields=" +  urllib.parse.quote(fields) + "&where=" +  urllib.parse.quote( " " + filter)
   
    #print( url+query)
    req = urllib.request.Request(url +  query)
    req.add_header('User-Agent', 
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0')

    return urllib.request.urlopen(req)



def print_shell():
    res = dblink.query_exec("select distinct type_c from decay_radiations order by 1")
    for r in res:
        print("SHELL_" + r[0] + " = '" + r[0]+ "'")

def print_transition():
    res = dblink.query_exec("select distinct  b_trans_type from decay_radiations order by 1")
    for r in res:
        print("TRANS_" + r[0] + " = '" + r[0]+ "'")