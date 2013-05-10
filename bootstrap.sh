#/usr/bin/bash
set -e
# packages needed: wget curl zlib-devel python gcc make
dir="$(readlink -e "$(dirname "$0")")"
mkdir -p $HOME/env
if [ -z "$TMPDIR" ] ; then
	export TMPDIR=$TMP
fi
cd $TMPDIR
if [ -z "$(which virtualenv)" ] ; then
	wget -nc --no-check-certificate https://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.9.1.tar.gz
	cd $TMPDIR
	tar xzf virtualenv-1.9.1.tar.gz
	cd virtualenv-1.9.1
	python setup.py install
fi
cd $dir
pwd
virtualenv env
ls env/bin/activate
source env/bin/activate
pip install -r requirements.txt
