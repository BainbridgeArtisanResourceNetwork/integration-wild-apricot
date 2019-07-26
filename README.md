#
pip install --upgrade pip
mkdir venv
mkdir data
virtualenv -p python3 venv
source ./venv/bin/activate
pip install -r requirements.txt
python --version
