# Fabric-ator
Soft robotic 3D printing

## Set Up
Clone the repo
``` bash
git clone https://github.com/ocrum/fabric-ator.git
cd fabric-ator
```
Install dependencies:
```bash
pip install -r requirements.txt
```

## Run

Start up the web server:
```bash
python src/app.py
```
Open the webserver:
http://127.0.0.1:5000
(or whatever flask says is server)


_Note: If it doesn't run correctly make sure that `matplotlib.use('Agg')` line 2 is commented out in `src/slice.py`_
