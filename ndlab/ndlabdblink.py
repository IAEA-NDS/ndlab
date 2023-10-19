
#%config IPCompleter.greedy = True
"""The Layer between the user and sqlite

Anything that uses the db connection is here. Users' request are received, passed to ndlaborm to build a sql
and executed here
"""

import os.path
import ndlaborm
import sqlite3
import traceback

class Dblink:
    
    """Whether to print the sql in case of error"""
    print_sql = True;
    print_debug = False;

    def __init__(self, db_path = ''):
        self._sqlbuilder = ndlaborm.Sqlbuilder()  

        if(os.path.exists(db_path) ):
            self._con_lite = sqlite3.connect(db_path)
            self.connected = True
        else:
            self._con_lite = None
            self.connected = False
            print("db path not found : " + os.path.abspath(os.path.join(db_path)))

        self.lastsql = ''
    

    def force_clean_query(self,force):
        """ Sets the flag for cleaning the query before parsing into the sql

        Just passing in to Sqlbilder
        """
        self._sqlbuilder.force_clean = force

    def query_exec(self,sql):
        """ Executes a sql query

        Just avoiding talking directly with the db connection
        """
        if(self.print_debug):
            print(sql)

        return self._con_lite.execute(sql)
        


    def _query_exec(self,fields, conditions=""):
        """From users' parameters parses an sql query, and executes it
        """
       
        try:
            return self.query_exec(self.query_build(fields, conditions))
        except:
            try:
             if(not self._sqlbuilder.force_clean):
                self.force_clean_query(True)
                sql = self.query_build(fields, conditions)
                self.force_clean_query(False)
                try:
                    return self.query_exec(sql)
                except sqlite3.Error as er:
                    exc_msg = (' '.join(er.args))
                    if(not self.print_sql):
                        exc_msg = ""

                    print('"Error, check the rules for the fields and filter parameters\n": %s' % exc_msg)
                    if(self.print_sql):
                        print(sql)
                    #print("Exception class is: ", er.__class__)
                    #print('SQLite traceback: ')
                    #exc_type, exc_value, exc_tb = sys.exc_info()
                    #print(traceback.format_exception(exc_type, exc_value, exc_tb))
            except:
                return None
            return None 
            
    def query_desc(self,fields, conditions=""):
        """ Tries to describe a query 

        interface to sqlbuilder
        """
        return self._sqlbuilder.query_desc(fields,conditions)
     
    def query_check(self,table, conditions=""):  
        """ Check if users parameters produce a valid query, return errors if any

        interface to sqlbuilder
        """
        
        return self._sqlbuilder.query_check(table, conditions)

    def is_query_ok(self,table, conditions=""):  
        """ Check if users parameters produce a valid query, return errors if any

        interface to sqlbuilder
        """
        return self._sqlbuilder.is_query_ok(table, conditions)
     
    def query_build(self,fields, conditions=""):
        """Produces an sql from users' parameters
        
        interface to sqlbuilder
        """
        self.lastsql = self._sqlbuilder.query_build(fields,conditions)
        return self.lastsql

    def _result_keys(self, result):
        """The keys of a result set
        """
        return [key[0] for key in result.description]
       

    def json_build(self, tablename , filter = ''):
        """Users interface to get the data in json
        """
        return self._json_build(self._query_exec(tablename , filter ))
              
    def _json_build(self, result):
        """From a result set builds the json
        """
       
        if(not result): return result
        
        keys = self._result_keys(result)

        field_name = []
        for k in keys:
           field_name.append( k + "\""+ ":\"" )
       
        jss = []
        i_range = range(len(keys))
        for r in result:
            tkks = ((( " {\"" if i == 0  else  " ,\"") +  field_name[i] + str(r[i]) + "\"" ) for i in i_range ) 
            jss.append(" ".join(tkks) + "}")

        return "[" + ",".join(jss) + "]"       

    def csv_build(self,tablename , filter = ''):
        """Users' interface to get the data in csv
        """
        return self._csv_build(self._query_exec(tablename, filter))

    def _csv_build(self, result, sep=","):
        """From a result set builds the csv
        """
       
        if(not result): return result
       
        keys = self._result_keys(result)
        jss = [sep.join(keys)]   
        i_range = range(len(keys))
        for r in result:
            jss.append(sep.join(( str(r[i]) if  str(r[i]) != 'None' else '')for i in i_range) )    
              
        return  "\n".join(jss)     

    def data_deliverer(self, return_type, fields, condition):
        """Users' interface to get the data in json or csv
        """
        res = "res"
        if(return_type == 'csv'):
            res = self.csv_build(fields, condition)
            if(res == None):
                return 'message \n error in the query'
        if( return_type == 'json'):
            res = self.json_build(fields, condition)
            if(res == None):
                return '{"message":"error in the query"}'
        return res


