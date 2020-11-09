import os
import re
import shutil
import subprocess
import sys

import pytest

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
input_path = os.path.join(modules_path, "tests/sku_create_input")
output_dir_path = os.path.join(modules_path, "tests/sku_create_input/Mellanox-SN2700-D48C8_NEW")
sku_def_file = os.path.join(input_path, "Mellanox-SN2700-D48C8.xml")
sku_create_script = os.path.join(scripts_path, "sonic_sku_create.py")
output_file_path = os.path.join(modules_path, "tests/sku_create_input/Mellanox-SN2700-D48C8_NEW/port_config.ini")
model_file_path = os.path.join(modules_path, "tests/sku_create_input/Mellanox-SN2700-D48C8/port_config.ini")

sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

class TestSkuCreate(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def are_file_contents_same(self,fname1,fname2):
        #Open the file for reading in text mode (default mode)
        f1 = open(fname1)
        f2 = open(fname2)

        #Read the first line from the files
        f1_line = f1.readline()
        f2_line = f2.readline()

        #Loop if either fname1 or fname2 has not reached EOF
        while f1_line!='' or f2_line!='':
            f1_line = re.sub('[\s+]','',f1_line)
            f2_line = re.sub('[\s+]','',f2_line)

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
    
    def test_no_param(self):
        if (os.path.exists(output_dir_path)):
            shutil.rmtree(output_dir_path)

        my_command = sku_create_script + " -f "  + sku_def_file  + " -d " + input_path

        #Test case execution without stdout
        result = subprocess.check_output(my_command,stderr=subprocess.STDOUT,shell=True)
        print result

        #Check if the Output file exists
        if (os.path.exists(output_file_path)):
            print("Output file: ",output_file_path,"exists. SUCCESS!")
        else:
            pytest.fail("Output file: {} does not exist. FAILURE!".format(output_file_path))

        #Check if the Output file and the model file have same contents
        if self.are_file_contents_same(output_file_path,model_file_path) == True:
            print("Output file: ",output_file_path," and model file: ",model_file_path,"contents are same. SUCCESS!")
        else:
            pytest.fail("Output file: {} and model file: {} contents are not same. FAILURE!".format(output_file_path,model_file_path))

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
