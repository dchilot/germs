
function cure()
# $1: directory in $INFECTION_ROOT to remove from the paths
# $2: r or recursive to also treat dependencies
{
	local _gloubi_clean_INFECTION_ROOT=
	local _gloubi_selected="$1"
	local _gloubi_recursive_cure=
	if [ -n "$2" -a "r" = "$2" -o "recursive" = "$2" ] ; then
		_gloubi_recursive_cure=1
	fi
	if [ -z "$INFECTION_ROOT" ] ; then
		INFECTION_ROOT="$HOME/env"
		_gloubi_clean_INFECTION_ROOT=1
	fi

	function _gloubi_cure_path()
	{
		local _path="$(eval echo "\$$2")"
		if [ -d "$1" -a -n "$(echo "$_path" | grep "$1")" ] ; then
			export $2="$(echo "$_path" | sed "s/:/\n/g" | grep -v "^$1\$" | sed ":loop;N;s/\n/:/;b loop")"
		fi
	}

	function _gloubi_cure()
	{
		_gloubi_cure_path $1/sbin PATH
		_gloubi_cure_path $1/bin PATH
		_gloubi_cure_path $1/lib LD_LIBRARY_PATH
		_gloubi_cure_path $1/lib64 LD_LIBRARY_PATH
		for mandir in $(find "$1" -type d -name man -prune) ; do
			_gloubi_cure_path "$1/$mandir" MANPATH
		done
		if [ -n "$_gloubi_recursive_cure" ] ; then
			if [ -d "$1/deps" ] ; then
				for dep in $1/deps/* ; do
					cure ${dep##*/} r
				done
			fi
		fi
	}

	if [ -n "$_gloubi_selected" ] ; then
		_gloubi_cure "$INFECTION_ROOT/$_gloubi_selected"
	else
		for dir in $(find "$INFECTION_ROOT" -mindepth 1 -maxdepth 1 -type d) ; do
			_gloubi_cure "$dir"
		done
	fi
	if [ -n "$_gloubi_clean_INFECTION_ROOT" ] ; then
		unset INFECTION_ROOT
	fi
}

