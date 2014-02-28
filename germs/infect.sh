
function infect()
# $1: directory in $INFECTION_ROOT to add to the paths
# $2: "front" to prepend to the paths (default is to append)
{
	local _gloubi_clean_INFECTION_ROOT=
	local _gloubi_selected="$1"
	local _gloubi_push_front=
	if [ -n "$2" -a "front" = "$2" ] ; then
		_gloubi_push_front=1
	fi
	if [ -z "$INFECTION_ROOT" ] ; then
		INFECTION_ROOT="$HOME/env"
		_gloubi_clean_INFECTION_ROOT=1
	fi

	function _gloubi_infect_path()
	{
		local _ok
		local _path="$(eval echo "\$$2")"
		if [ -d "$1" ] ; then
			if [ -z "$(echo "$_path" | sed "s/:/\n/g"| grep "^$1\$")" ] ; then
				if [ -n "$_path" ] ; then
					if [ -n "$_gloubi_push_front" ] ; then
						export $2="$1:$_path"
					else
						export $2="$_path:$1"
					fi
				else
					export $2="$1"
				fi
			fi
			_ok=0
		else
			_ok=1
		fi
		return $_ok
	}

	function _gloubi_infect()
	{
		local _infected=
		_gloubi_infect_path $1/sbin PATH && _infected=1
		_gloubi_infect_path $1/bin PATH && _infected=1
		for lib_path in LD_LIBRARY_PATH LIBRARY_PATH ; do
			_gloubi_infect_path $1/lib $lib_path && _infected=1
			_gloubi_infect_path $1/lib64 $lib_path && _infected=1
			_gloubi_infect_path $1/lib/pkgconfig $lib_path && _infected=1
			_gloubi_infect_path $1/lib64/pkgconfig $lib_path && _infected=1
		done
		_gloubi_infect_path $1/lib/pkgconfig PKG_CONFIG_PATH && _infected=1
		_gloubi_infect_path $1/lib64/pkgconfig PKG_CONFIG_PATH && _infected=1
		for mandir in $(find "$1" -type d -name man -prune) ; do
			_gloubi_infect_path "$1/$mandir" MANPATH && _infected=1
		done
		if [ -d "$1/deps" ] ; then
			for dep in $1/deps/* ; do
				infect ${dep##*/}
			done
		fi
		if [ -z "$_infected" ] ; then
			echo "could not infect $1" >&2
		fi
	}

	if [ -n "$_gloubi_selected" ] ; then
		_gloubi_infect "$INFECTION_ROOT/$_gloubi_selected"
	else
		for dir in $(find "$INFECTION_ROOT" -mindepth 1 -maxdepth 1 -type d) ; do
			_gloubi_infect "$dir"
		done
	fi
	if [ -n "$_gloubi_clean_INFECTION_ROOT" ] ; then
		unset INFECTION_ROOT
	fi
}

