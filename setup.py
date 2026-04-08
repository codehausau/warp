from setuptools import setup, find_packages
import subprocess

about = {}
with open('warp/version.py', 'r', encoding='utf8') as file:
    exec(file.read(), about)

def getRequirements():
    with open('requirements.txt', 'r') as file:
        return file.readlines()

    return []

#def getVersion():
#
#    subprocess.run(['git','update-index','--refresh'], \
#        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#
#    dirty = subprocess.run(['git','diff-index','--quiet','HEAD']) \
#                .returncode != 0
#    dirtyStr = "-dirty" if dirty else ""
#
#    githash = subprocess.run(['git','rev-parse','--short','HEAD'], \
#            check=True, capture_output=True, text=True) \
#            .stdout.rstrip()
#
#    return f"{about['VERSION']}-{githash}{dirtyStr}"


setup(
    name='warp',
    packages=find_packages(),
    version=about['get_version'](),
    include_package_data=True,
    install_requires=getRequirements(),
)
