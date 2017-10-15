srpm:
	dnf -y install tito
	tito build --test --srpm --output=$(outdir)
	touch $(outdir)/$(spec)
