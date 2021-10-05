import json
import os
import re
import shutil
import subprocess
import sys

import pytest

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

# xml file input related test resources
xml_input_paths = ["tests/sku_create_input/2700_files", "tests/sku_create_input/7050_files", "tests/sku_create_input/7260_files"]
output_xml_dir_paths = [
    "tests/sku_create_input/2700_files/Mellanox-SN2700-D48C8_NEW/",
    "tests/sku_create_input/7050_files/Arista-7050CX3-32S-D48C8_NEW",
    "tests/sku_create_input/7260_files/Arista-7260CX3-D108C8_NEW"
]
sku_def_files = ["Mellanox-SN2700-D48C8.xml", "Arista-7050CX3-32S-D48C8.xml", "Arista-7260CX3-D108C8.xml"]
output_xml_file_paths = [
    "tests/sku_create_input/2700_files/Mellanox-SN2700-D48C8_NEW/port_config.ini",
    "tests/sku_create_input/7050_files/Arista-7050CX3-32S-D48C8_NEW/port_config.ini",
    "tests/sku_create_input/7260_files/Arista-7260CX3-D108C8_NEW/port_config.ini"
]
model_xml_file_paths = [
    "tests/sku_create_input/2700_files/Mellanox-SN2700-D48C8/port_config.ini",
    "tests/sku_create_input/7050_files/Arista-7050CX3-32S-D48C8/port_config.ini",
    "tests/sku_create_input/7260_files/Arista-7260CX3-D108C8/port_config.ini"
]

minigraph_input_path = os.path.join(modules_path, "tests/sku_create_input/3800_files")
output_minigraph_dir_path = os.path.join(modules_path, "tests/sku_create_input/3800_files/Mellanox-SN3800-D28C50_NEW/")
minigraph_file = os.path.join(minigraph_input_path, "t0-1-06-minigraph.xml")
output_minigraph_file_path = os.path.join(modules_path, "tests/sku_create_input/3800_files/Mellanox-SN3800-D28C50_NEW/port_config.ini")
model_minigraph_file_path = os.path.join(modules_path, "tests/sku_create_input/3800_files/Mellanox-SN3800-D28C50/port_config.ini")
config_db_input_path = os.path.join(modules_path, "tests/sku_create_input/2700_files")
output_config_db_dir_path = os.path.join(modules_path, "tests/sku_create_input/2700_files/Mellanox-SN2700-C28D8/")
config_db_file = os.path.join(config_db_input_path, "config_db.json")
output_config_db_file_path = os.path.join(modules_path, "tests/sku_create_input/2700_files/Mellanox-SN2700-C28D8/port_config.ini")
model_config_db_file_path = os.path.join(modules_path, "tests/sku_create_input/2700_files/Mellanox-SN2700-C28D8-ORIG/port_config.ini")
port_split_input_path = os.path.join(modules_path, "tests/sku_create_input/2700_files")
port_split_output_path = os.path.join(modules_path, "tests/sku_create_input/port_split_files")
port_split_config_db_output_file_path = os.path.join(port_split_output_path, "config_db.json")
port_split_pc_ini_file_output_path = os.path.join(port_split_output_path, "port_config.ini")
port_unsplit_input_path = os.path.join(modules_path, "tests/sku_create_input/2700_files")
port_unsplit_output_path = os.path.join(modules_path, "tests/sku_create_input/port_unsplit_files")
port_unsplit_config_db_output_file_path = os.path.join(port_unsplit_output_path, "config_db.json")
port_unsplit_pc_ini_file_output_path = os.path.join(port_unsplit_output_path, "port_config.ini")
sku_create_script = "sonic_sku_create.py"

sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

class TestSkuCreate(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path

    def are_file_contents_same(self,fname1,fname2):
        #Open the file for reading in text mode (default mode)
        f1 = open(fname1)
        f2 = open(fname2)

        #Read the first line from the files
        f1_line = f1.readline()
        f2_line = f2.readline()

        #Loop if either fname1 or fname2 has not reached EOF
        while f1_line!='' or f2_line!='':
            f1_line = re.sub(r'[\s+]', '', f1_line)
            f2_line = re.sub(r'[\s+]', '', f2_line)

            if f1_line!=f2_line:
                f1.close()
                f2.close()
                return False
            else:
                f1_line = f1.readline()
                f2_line = f2.readline()

        f1.close()
        f2.close()
        return True
    
    def test_sku_from_xml_file(self):
        test_resources = zip(xml_input_paths, output_xml_dir_paths, sku_def_files, output_xml_file_paths, model_xml_file_paths)
        for xml_input_path, output_xml_dir_path, sku_def_file, output_xml_file_path, model_xml_file_path in test_resources:
            xml_input_path = os.path.join(modules_path, xml_input_path)
            output_xml_dir_path = os.path.join(modules_path, output_xml_dir_path)
            sku_def_file = os.path.join(xml_input_path, sku_def_file)
            output_xml_file_path = os.path.join(modules_path, output_xml_file_path)
            model_xml_file_path = os.path.join(modules_path, model_xml_file_path)

            if (os.path.exists(output_xml_dir_path)):
                shutil.rmtree(output_xml_dir_path)

            my_command = sku_create_script + " -f "  + sku_def_file  + " -d " + xml_input_path

            #Test case execution without stdout
            result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
            print(result)

            #Check if the Output file exists
            if (os.path.exists(output_xml_file_path)):
                print("Output file: ",output_xml_file_path, "exists. SUCCESS!")
            else:
                pytest.fail("Output file: {} does not exist. FAILURE!".format(output_xml_file_path))

            #Check if the Output file and the model file have same contents
            if self.are_file_contents_same(output_xml_file_path, model_xml_file_path) == True:
                print("Output file: ",output_xml_file_path, " and model file: ",model_xml_file_path, "contents are same. SUCCESS!")
            else:
                pytest.fail("Output file: {} and model file: {} contents are not same. FAILURE!".format(output_xml_file_path, model_xml_file_path))

    def test_sku_from_minigraph_file(self):
        if (os.path.exists(output_minigraph_dir_path)):
            shutil.rmtree(output_minigraph_dir_path)

        my_command = sku_create_script + " -m "  + minigraph_file  + " -d " + minigraph_input_path

        #Test case execution without stdout
        result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
        print(result)

        #Check if the Output file exists
        if (os.path.exists(output_minigraph_file_path)):
            print("Output file: ",output_minigraph_file_path, "exists. SUCCESS!")
        else:
            pytest.fail("Output file: {} does not exist. FAILURE!".format(output_minigraph_file_path))

        #Check if the Output file and the model file have same contents
        if self.are_file_contents_same(output_minigraph_file_path, model_minigraph_file_path) == True:
            print("Output file: ",output_minigraph_file_path, " and model file: ",model_minigraph_file_path, "contents are same. SUCCESS!")
        else:
            pytest.fail("Output file: {} and model file: {} contents are not same. FAILURE!".format(output_minigraph_file_path, model_minigraph_file_path))

    def test_sku_from_config_db_file(self):
        if (os.path.exists(output_config_db_dir_path)):
            shutil.rmtree(output_config_db_dir_path)

        my_command = sku_create_script + " -j "  + config_db_file  + " -d " + config_db_input_path

        #Test case execution without stdout
        result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
        print(result)

        #Check if the Output file exists
        if (os.path.exists(output_config_db_file_path)):
            print("Output file: ",output_config_db_file_path, "exists. SUCCESS!")
        else:
            pytest.fail("Output file: {} does not exist. FAILURE!".format(output_config_db_file_path))

        #Check if the Output file and the model file have same contents
        if self.are_file_contents_same(output_config_db_file_path, model_config_db_file_path) == True:
            print("Output file: ",output_config_db_file_path, " and model file: ",model_config_db_file_path, "contents are same. SUCCESS!")
        else:
            pytest.fail("Output file: {} and model file: {} contents are not same. FAILURE!".format(output_config_db_file_path, model_config_db_file_path))

    def test_sku_port_split(self):
        if (not os.path.exists(config_db_file)):
            pytest.fail("Input config_db.json file does not exist. Exitting...")
            return
        else:
             shutil.copyfile(config_db_file, port_split_config_db_output_file_path)
        
        if (not os.path.exists(model_config_db_file_path)):
            pytest.fail("Input port_config.ini file does not exist. Exitting...")
            return
        else:
             shutil.copyfile(model_config_db_file_path, port_split_pc_ini_file_output_path)
           
        my_command = sku_create_script + " -s Ethernet16 2x50 -d " + port_split_input_path + " -q " + port_split_output_path

        #Test case execution without stdout
        result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
        print(result)

        #Verify the output of port_config.ini file
        eth16_found = False
        eth18_found = False

        f_in = open(port_split_pc_ini_file_output_path, 'r')

        for line in f_in.readlines():
            port_info = line.split()
            eth16_info = ['Ethernet16', '16,17', 'etp5a', '5', '50000']
            eth18_info = ['Ethernet18', '18,19', 'etp5b', '5', '50000']

            if port_info == eth16_info:
                eth16_found = True
      
            if port_info == eth18_info:
                eth18_found = True

            if eth16_found and eth18_found:
                break 
      
        if eth16_found and eth18_found:
            print("Success: Port split information found in port_config.ini file")
        else:
            pytest.fail("Failure: Port split information not found in port_config.ini file")
            return

        #Verify the output of config_db.json
        with open(port_split_config_db_output_file_path) as f:
            data = json.load(f)
     
        eth16_dict = {u'alias': u'etp5a', u'lanes': u'16,17', u'speed': 50000, u'mtu': u'9100'}
        eth16_instance = data['PORT'].get("Ethernet16")
        if eth16_instance is None:
            pytest.fail("Failure: Port split information not found in config_db.json file")
            return
        else:
            if eth16_instance != eth16_dict:
                pytest.fail("Failure: Port split information not found in config_db.json file")
                return

        eth18_dict = {u'alias': u'etp5b', u'lanes': u'18,19', u'speed': 50000, u'mtu': u'9100'}
        eth18_instance = data['PORT'].get("Ethernet18")
        if eth18_instance is None:
            pytest.fail("Failure: Port split information not found in config_db.json file")
            return
        else:
            if eth18_instance != eth18_dict:
                pytest.fail("Failure: Port split information not found in config_db.json file")
                return

        print("Success: Port split information found in config_db.json file")

    def test_sku_port_unsplit(self):
        if (not os.path.exists(config_db_file)):
            pytest.fail("Input config_db.json file does not exist. Exitting...")
            return
        else:
             shutil.copyfile(config_db_file, port_unsplit_config_db_output_file_path)
        
        if (not os.path.exists(model_config_db_file_path)):
            pytest.fail("Input port_config.ini file does not exist. Exitting...")
            return
        else:
             shutil.copyfile(model_config_db_file_path, port_unsplit_pc_ini_file_output_path)
           
        my_command = sku_create_script + " -s Ethernet112 1x100 -d " + port_unsplit_input_path + " -q " + port_unsplit_output_path

        #Test case execution without stdout
        result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
        print(result)

        #Verify the output of port_config.ini file
        eth112_found = False

        f_in = open(port_unsplit_pc_ini_file_output_path, 'r')

        for line in f_in.readlines():
            port_info = line.split()
            eth112_info = ['Ethernet112', '112,113,114,115', 'etp29', '29', '100000']
            if port_info == eth112_info:
                eth112_found = True
                break
      
        if eth112_found:
            print("Success: Port split information found in port_config.ini file")
        else:
            pytest.fail("Failure: Port split information not found in port_config.ini file")
            return

        #Verify the output of config_db.json
        with open(port_unsplit_config_db_output_file_path) as f:
            data = json.load(f)
     
        eth112_dict = {'alias': 'etp29', 'lanes': '112,113,114,115', 'speed': 100000, 'mtu': u'9100'}
        eth112_instance = data['PORT'].get("Ethernet112")
        if eth112_instance is None:
            pytest.fail("Failure: Port split information not found in config_db.json file")
            return
        else:
            if eth112_instance != eth112_dict:
                pytest.fail("Failure: Port split information not found in config_db.json file")
                return

        print("Success: Port split information found in config_db.json file")

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
