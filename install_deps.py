# install_deps.py
import subprocess
import sys

def install_packages():
    """Install specific compatible package versions"""
    packages = [
        "psycopg2-binary==2.9.7",
        "pysnmp==4.4.12", 
        "pyasn1==0.4.8",
        "schedule==1.2.0"
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"Successfully installed: {package}")
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {e}")

if __name__ == "__main__":
    install_packages()