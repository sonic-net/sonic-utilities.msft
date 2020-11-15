
""" Common test utilities """

import subprocess


def get_result_and_return_code(cmd):
    return_code = 0
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        return_code = e.returncode
        # store only the error, no need for the traceback
        output = e.output.strip().split("\n")[-1]

    print(output)
    return(return_code, output)
