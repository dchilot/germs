#/usr/bin/sh
# packages needed: wget curl zlib-devel python gcc make
dir="$(readlink -e "$(dirname "$0")")"
mkdir -p $HOME/env
if [ -z "$TMPDIR" ] ; then
	export TMPDIR=$TMP
fi
cd $TMPDIR
#export PATH=$PATH:$HOME/env/pythonbrew/bin
#export PYTHONBREW_ROOT=$HOME/env/pythonbrew
#if [ -z "$(which pythonbrew)" ] ; then
	#echo "Install pythonbrew"
	#curl -kLO http://xrl.us/pythonbrewinstall
	#chmod +x pythonbrewinstall
	#./pythonbrewinstall
#fi
#source $HOME/env/pythonbrew/etc/bashrc
#which pythonbrew
#PYTHON_VERSION=2.7
#pythonbrew install $PYTHON_VERSION
#pythonbrew switch $PYTHON_VERSION
if [ -z "$(which virtualenv)" ] ; then
	#wget -nc --no-check-certificate http://pypi.python.org/packages/source/d/distribute/distribute-0.6.36.tar.gz
	wget -nc --no-check-certificate https://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.9.1.tar.gz
	cd $TMPDIR
	tar xzf virtualenv-1.9.1.tar.gz
	cd virtualenv-1.9.1
	python setup.py install
fi
cd $dir
virtualenv env
source env/bin/activate
#pip install $TMPDIR/distribute
pip install -r requirements.txt
