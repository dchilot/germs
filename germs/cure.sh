
function cure()
# $1: directory in $INFECTION_ROOT to remove from the paths
# $2: r or recursive to also treat dependencies
{
	local _gloubi_INFECTION_ROOT=
	local _gloubi_selected="$1"
	local _gloubi_recursive_cure=
	local _gloubi_direct=
	if [ -n "$2" -a "r" = "$2" -o "recursive" = "$2" ] ; then
		_gloubi_recursive_cure=1
	fi
	if [[ $_gloubi_selected == /* ]] ; then
		# special case: infect the folder directly
		_gloubi_direct=1
	else
		if [ -n "$INFECTION_ROOT" ] ; then
			_gloubi_INFECTION_ROOT=$INFECTION_ROOT
		else
			_gloubi_INFECTION_ROOT="$HOME/env"
		fi
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
		for idir in "$1" "$1/usr" ; do
			if [ -d "$idir" ] ; then
				_gloubi_cure_path $idir/sbin PATH
				_gloubi_cure_path $idir/bin PATH
				_gloubi_cure_path $idir/lib LD_LIBRARY_PATH
				_gloubi_cure_path $idir/lib64 LD_LIBRARY_PATH
				for lib_path in LD_LIBRARY_PATH LIBRARY_PATH ; do
					_gloubi_cure_path $idir/lib $lib_path
					_gloubi_cure_path $idir/lib64 $lib_path
					_gloubi_cure_path $idir/lib/pkgconfig $lib_path
					_gloubi_cure_path $idir/lib64/pkgconfig $lib_path
				done
				_gloubi_cure_path $idir/lib/pkgconfig PKG_CONFIG_PATH
				_gloubi_cure_path $idir/lib64/pkgconfig PKG_CONFIG_PATH
				for mandir in $(find "$idir" -type d -name man -prune) ; do
					_gloubi_cure_path "$idir/$mandir" MANPATH
				done
			fi
		done
		if [ -n "$_gloubi_recursive_cure" ] ; then
			if [ -d "$1/deps" ] ; then
				for dep in $1/deps/* ; do
					cure ${dep##*/} r
				done
			fi
		fi
	}

	if [ -n "$_gloubi_direct" ] ; then
		_gloubi_cure "$_gloubi_selected"
	elif [ -n "$_gloubi_selected" ] ; then
		_gloubi_cure "$_gloubi_INFECTION_ROOT/$_gloubi_selected"
	else
		for dir in $(find "$_gloubi_INFECTION_ROOT" -mindepth 1 -maxdepth 1 -type d) ; do
			_gloubi_cure "$dir"
		done
	fi
	hash -r
}

