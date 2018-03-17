export libdir="$(builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd)"

die() {
	echo "fail."; exit 1; 
}

function runcmd {
	bash -c "set -x; $libdir/../prunerepo --verbose $*;" 
}

function listpkgsbyrepo {
	dnf repoquery --repofrompath=test_prunerepo,$testrepo --repo=test_prunerepo --refresh --quiet --queryformat '%{location}' | sort
}

function listpkgsbyfs {
	find . -name '*.rpm' | cut -c 3- | sort
}

function run {
	echo '>' $@;
	eval $@;
}

function setup {
	rm -r $testrepo
	cp -r $origrepo $testrepo
	cd $testrepo
}
