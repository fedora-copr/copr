# Copr

[**Project Page**](https://fedorahosted.org/copr/) | 
[**Report a Bug**](https://bugzilla.redhat.com/enter_bug.cgi?product=Copr) | 
[**Production Instance**](https://copr.fedoraproject.org) | 
[**Testing Instance**](http://copr-fe-dev.cloud.fedoraproject.org/)

Copr is a Fedora community build service in [Fedora](https://getfedora.org/) that builds your open-source project and creates your own RPM repository.

<img src="/doc/img/copr-workflow.png" width="400px">

## Using Copr
Learn [how to use Copr](https://developer.fedoraproject.org/deployment/copr/about.html) and [how to create RPM packages](https://developer.fedoraproject.org/deployment/rpm/about.html) on the [Fedora Developer Portal](https://developer.fedoraproject.org).


## Local Testing Environment
You can use [Vagrant](https://developer.fedoraproject.org/tools/vagrant/about.html) to run your local test environment. We currently support *frontend* and *dist-git*.

```
$ git clone https://github.com/fedora-copr/copr.git
$ cd copr
$ vagrant up
```

For more information see [our wiki page](https://fedorahosted.org/copr/wiki/Contribute#LocalDevelopmentEnvironment).
