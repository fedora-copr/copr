.. _git_guide:

`Git <http://git.or.cz/>`_ Guide
================================

Copr git web interface
----------------------

If you just want to browse our git repository use https://pagure.io/copr/copr.

Getting Started
---------------

A quick start guide to using git, especially if you're used to using SVN or CVS.

Install Git
-----------

To install git on Fedora just::

  # dnf -y install git

For installation on RHEL you have to add repository. For example for RHEL6 it is::

  # rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm

For other versions see http://download.fedoraproject.org/pub/epel directory. Then you can install git as usual.

Clone the Copr git repository
-----------------------------

For anonymous access to the Copr source code, feel free to clone the repository::

    git clone https://pagure.io/copr/copr

Copr committers can clone the repository using the ssh url, which is required if you want to push changes into the repo (and of course you need permission to do so)::

    git clone ssh://git@pagure.io/copr/copr.git

For more details check out the DownloadIt page. 

Commit Access
-------------

If you have been approved to get git commit access to the copr git repository you'll need to do the following:

- Get your ssh RSA key into the Fedora accounts system here: (note: use your login name in this url :))

https://accounts.fedoraproject.org/user/USERNAME/settings/keys

- After that you should be able to git clone with::

    git clone ssh://git@pagure.io/copr/copr.git

Identify Yourself
-----------------

You must configure your name and email address for git to apply it to your commits. There are several ways to do this but one is to do so in ``~/.gitconfig``.

**NOTE:** git can differentiate between the author of a commit and person with commit access pushing it to the repository. Most of the time these are the same, but in the case of accepting patches from the community the author should be modified (via setting the ``GIT_AUTHOR_NAME`` and ``GIT_AUTHOR_EMAIL`` environment variables) while keeping your commit user as yourself.

A good sample ``~/.gitconfig``::

    [user]

        name = Bill Smith

        email = billsmith@example.com



    [alias]

        ci = commit -a

        co = checkout

        st = status -a

        praise = blame 



    [apply]

        whitespace = strip



    [diff]

        color = auto

        rename = copy 



    [pager]

        color = true 



    [status]

        color = auto

Things To Remember
------------------

1) Try to work in local branches and use master (or other tracking branches) just for pushing/pulling changes.

2) Your git commits are local only until you push them to the remote repository (or submit a patch if you do not have commit access).

3) Always run ``gitk --all`` (or tig) before you push changes. Examine what will be pushed so you can address anything unexpected before you push. (after which the commit is for all intents and purposes, permanent)

Everyday Workflow
-----------------

Ready to start hacking on the code? Create yourself a branch to work in::

    git checkout -b mybugfix

This is actually combining two steps into one, you could also do this the long way with::

    git branch mybugfix      # create the branch

    git checkout mybugfix    # work on this branch

The branch will be created from your current location, i.e. if you currently have master checked out your branch will point to the same commit as was the HEAD of master at that time.

List your branches anytime and see which you're working on with::

  git branch                # list all your branches


You now have a local branch nobody else can see, they're extremely fast and lightweight, and you can commit as you please. Nothing is pushed to the central repository until you explicitly do so.

Note that the single directory you cloned can be used to work on any branch you like with a simple git checkout command. Switching branches is extremely fast and easy and you can do so at virtually any time. Even if you have changes you don't want to commit (which you often can anyhow as you're working in a private branch), you can use git-stash to stash them away and apply them later, possibly to another branch. (if you found yourself working on the wrong branch)::

    git stash save "Half finished fixes for epoch bug."

Now that you've branched you can get to work modifying, adding, and deleting files similar to the way you would use svn::

    echo "blahblahblah" > newfile

    git add newfile

    git-rm Worker.java 

    rm 'java/code/src/com/redhat/rhn/manager/Worker.java'

    git status

    # On branch master

    # Changes to be committed:

    #   (use "git reset HEAD <file>..." to unstage)

    #

    #       deleted:    Worker.java

    #       new file:   newfile

    #

    # Changed but not updated:

    #   (use "git add <file>..." to update what will be committed)

    #

    #       modified:   SatManager.java

    #

Now it's time to commit (and you can and should commit often, as often as you like). 

**IMPORTANT NOTE:** By default, files you have modified will not be included if you run ``git commit``. Normally you will probably just want to use the -a option to commit all modified files::

    git commit -a

If you wish to only include **some** of the modified files in your commit, you must do something like::

    git commit modified-file1.txt modified-file3.txt

Repeat for as many commits as you like on your branch until you're satisfied with your bugfix, feature, or whatever.

Commit Messages
---------------

We have a convention for our commits.  The simple rule is:

If you are working on a bugzilla or a feature (that should have a bugzilla associated with it) you should prepend your commit message with the bugzilla # followed by your message describing the commit::

    BUGZILLA# - comment goes here

For example::

    461162 - just add all the networks to the system profile in cobbler

If you are not working on a bugzilla in relation to the change just type your message as normal.

Pushing Changes
---------------

NOTE: These instructions apply to those with commit access.

When the time comes to push the changes in your local branch out to the repository, we need to pull down any changes others have pushed since we created that branch and resolve conflicts if necessary. There are two tools to do this, merge and rebase, but for smaller individual changes we will use rebase.

Git rebase essentially checks what commits are in some destination branch that your local branch does not have, what commits are in your local branch that aren't in the destination, then pulls down the new remote commits and re-applies your commits on top of it. It essentially re-does your work again patch by patch, on top of the latest state of the destination branch. (usually master)

To push your fixes in 'mybugfix' out you would do the following::

    git checkout master           

    git merge mybugfix            # merge in the commits from your local branch (use --squash if you'd like 1 to fold them into one commit)

    git pull --rebase             # pull latest commits down from master, re-apply ours on top

    gitk --all                    # review the status of the repository (can also use "tig" command for this)

    git push origin master        # push commits from local branch master to remote branch with the same name

Working Directly In Master
--------------------------

If you feel you cannot keep track of local branches (or just do not want to use them), you can work directly in your master tracking branch. Please, just be sure to use the --rebase option when you have unpushed changes committed and go to pull from master::

    git pull --rebase

Not using --rebase means that git pull will merge the remote references in instead, resulting in many of the dreaded "merge commits" in the git history which clutter up the log unnecessarily.

Note that using local branches offers some substantial benefits and is the recommended approach, see Understand Branches section below for more.

Submitting Patches
------------------

For those without commit access, or those who just prefer to submit a patch for review, the steps are as follows::

    git checkout master                 

    git pull                      # fetch latest remote changes into master (should apply clean)

    git checkout mybugfix         # return to your branch

    git rebase master             # re-apply you changes on top of current state of master

    git format-patch master       # generate a patch against master

This will generate a number of patch files, one for each commit in your branch, which you can then submit to the copr-devel mailing list where they can be reviewed and accepted.

Applying Patches
----------------

Applying patches is as simple as::

    git am 0001-incoming.patch       # apply the patch in your current branch

Note that if you examine the git log, both the git identity of the patch author and the patch committer are tracked.

Understanding Branches
----------------------

The use of branches has proven one of the more difficult things to adapt to for those coming from non-distributed scm's like subversion. 

* Branches can be local (only in your git clone) or remote (i.e. they exist in the remote repository).

* List local branches with ``git branch``, remote branches with ``git branch -r``.

* When listing remote branches you'll see things like "origin/master". Origin is a default remote reference created when you do a git clone of some remote repository. Because git is designed for highly distributed workflow, it is possible to actually have MANY remote references configured within one git repository and push/pull from them all to collaborate with others. For our situation however all you really need to know is that "origin" is a remote reference to the copr git repository, thus origin/master refers to the remote master branch.

* After doing a git clone, a local "master" branch is configured for you as a tracking branch for origin/master. You can create other tracking branches easily with::
   
    git checkout --track -b mylocalbranch origin/someremotebranch
    
  ...commonly used to work release or feature branches

* If you git checkout origin/somebranch you've checked out a pointer to a remote branch, and thus you cannot commit here. (git will indicate this clearly) If you wish to make some modifications you just need to create a local branch off of that commit with '''git checkout -b mybranch'''.

* The main advantage to working in local branches is context switching. If working in a local branch and something comes up, (you need to go to master and look at something, fix a bug in some release branch, change to some other urgent task, etc.) just commit your work (or stash it) and go about your business. Return to your branch when you wish to resume work.

Managing Remote Branches
------------------------

See what remote branches exist::

    git branch -r

Create a new remote branch (based on an existing local branch)::

    git-push origin localbranch:refs/heads/newremotebranch

Checkout a local copy of a remote branch, originally you will need to track it so you can keep up with changes automatically. (consider this like your local "master" branch, except push/pull works against the remote branch instead of the remote master)::

    git checkout --track -b localbranch origin/remotebranch

Push latest changes from your local branch back to the remote branch::

    git-push origin localbranch:remotebranch

If you ever want to use that branch again, you can just do::

    git-checkout my-branchname

As with any long lived branch it's important to sync it with master periodically to prevent a merge disaster when you rejoin. In the case of long lived branches, use ``git merge`` instead of ``git rebase``::

    git checkout master

    git pull

    git checkout myremotetrackingbranch

    git merge master

Deleting a remote branch entirely: For all intents and purposes lets leave remote branches for the time being. Deleting them can be a little dangerous if you were to happen to do it on a RELEASE branch, and send us digging into scm backups to recover it. Check with someone if you have a temporary remote branch that you really want deleted. Otherwise we'll probably clean them up from time to time.

* It is a very good idea to treat your tracking branches as you do master. I.e. *do not* work directly in them, but rather create local branches off them to do your work and only use the tracking branch for pulling down changes and then merging in your work and immediately pushing it out.

* Running "git push" without specifying the branches as per the above syntax will cause git to attempt to push your local commits from all tracked remote branches back to their respective remote counterparts. This is definitely counterintuitive. However if you only use tracking branches for pushing/pulling changes and instead work in local branches, this will not be an issue for you. Use the recommended ``git push origin master:master`` syntax to be specific.

* You will see git pull fetching information about other remote branches, please note this is not applying those commits in your local tracking branch, it's just updating internal info and noticing that something has changed in the remote repo. Only the current branch will have it's changes applied.

Difference Between Merge and Rebase
-----------------------------------

Consider the following two branches with some commits:

Branch 1: A -> B -> C -> D -> E

Branch 2: A -> B -> C -> C1 -> C2

Here Branch 2 was created off of Branch 1 at the point in time when commit C was the most recent.

If we were to merge Branch 2 directly into Branch 1 (git checkout branch1 && git merge branch2) we could end up with:

Branch 1: A -> B -> C -> D -> E -> C1 -> C2 -> MC

Where MC is a "merge commit" identifying that a merge took place, what files were involved, and most importantly what files conflicted and had to be resolved.

If however we ran a rebase first (git checkout branch2 && git rebase branch1 && git checkout branch1 && git merge branch2) we would end up with the following:

Branch 1: A -> B -> C -> D -> E -> E1 -> E2

Where E1 and E2 are the commits previously known as C1 and C2, but re-applied on top of commit E instead.

The key difference is that rebase re-applies the new commits on top of the current state of the tree, whereas merge brings them in and adds them to the history, plus a merge commit. Rebase is generally much better (cleaner history) for small individual changes, while we frequently use merge for long lived release/feature branches that are not so simple.

Resolving Conflicts
-------------------

Git will normally merge just about anything that can be safely automatically merged but conflicts can still occur. If you get the dreaded ''Automatic merge failed; fix conflicts and then commit the result.'' during a merge, here is how you can go about resolving it.

First list the files that require merging::

    git ls-files --unmerged

Choose a file, open it, and search for the conflict markers just as you would when resolving a svn conflict.

If the conflict is not obvious you can use gitk to view ONLY the commits made in each branch that are resulting in your conflict::

    gitk --merge path/to/file

If you'd like try a three way merge, try::

    git mergetool -t meld

This will fire up a merge tool (in my case "meld") with three columns. On the left will be the file as it was in your current branch, in the middle the state of the file now (after automatic merging including conflict markers), and on the left the state of the file from the branch being merged in.

Once you've resolved your conflict::

    git add path/to/resolved/file

And proceed to the next file.

Once you've resolved all conflicts::

    git commit -a

Git will pre-populate the commit message with the data for your merge commit including what files conflicted. Add anything you feel is necessary and you're ready to push out your changes.

Cleaning Up A Confused Git Tree
-------------------------------

If you run into a situation where your git tree is seemingly confused and you cannot pull or checkout another branch, here are the steps you can take to correct it. This can sometimes happen when files in your checkout are owned by root (seems to be happening for some users using our devel setup) or when a merge or pull encounters conflicts that are never resolved.

1. Make sure you don't actually *need* any of the files that git shows as modified or untracked, because these steps below '''will delete them'''.

2. Make sure all files in your git tree are owned by the correct user.

3. Get rid of modified files by resetting your tree to the last known commit for the branch you're on: '''git reset --hard HEAD'''

4. Cleanup files git lists as untracked with: ``git clean -xfd`` (be careful here, this will delete any untracked files in your checkout) If you want to keep some of them, back them up or remove untracked files manually.

5. Verify your git tree is now clean, then try to git pull or git checkout as you were before.


Other Common Tasks
------------------

Revert a file with uncommitted changes you do not wish to keep::

    git checkout path/to/file/to/revert.txt

Revert all your current uncommitted changes::

    git reset --hard HEAD

Revert changes from a past commit (generates a new commit)::

    git revert a31f80910768ba2232c796b814be11d064421f19

View diff of changes in a past commit::

    git show a31f80910768ba2232c796b814be11d064421f19

View diff of changes between two past commits::

    git diff baf1a1490e205f821fbcc9c4ec2581728afd1c14..a31f80910768ba2232c796b814be11d064421f19

View a part revision of a specific file (feel free to pipe the output somewhere if you like). Make sure to use the full path to the file as it would be from the root of your git repository::

    git show SHA1:java/code/src/com/redhat/rhn/common/db/datasource/xml/Channel_queries.xml

Replace file with a past version. Note that after doing this you still need to commit the change::

    git checkout SHA1 -- path/to/file

Once you make changes, you can see the differences you've made since last commit::

    git diff HEAD

The following commands can help with formatting patches::

    git-format-patch

    git-send-email

Finished with your branch? Want to get rid of it? Then::

    git branch -d mybranch

If you get a warning about unmerged changes, you can force the removal with::

    git branch -D mybranch

See what you have committed but not pushed::

    git log --pretty=oneline origin/master..master

Ever find yourself working on something then have to go fix a bug? You can stash away your files, fix your bug, then go back to what you were doing.

Save your work::

    git stash save mymessage

FIX YOUR BUG, commit and push. See what you have stashed::

    git stash list

    git stash apply stash@{0}

Tips
----

* Install '''tig''' for a very handsome mutt-like command line app for browsing git history and diffs.


* Install '''gitk''' for a brutally ugly yet still rather useful graphical tool for doing the same thing.


* Keep track of what branch you are in by looking at your prompt. Update your prompt as follows::

    PS1="`\W\$(git branch 2> /dev/null | grep -e '\* ' | sed 's/^..\(.*\)/{\1}/') <\u@\h>`_\$ "

Here is what you will see when you cd into a git repository::

    [speedy@gonzalez copr{master}]$

If you chdir to a non git repository, you're prompt will look as normal::

    [speedy@gonzalez ~]$ 

Building Test RPMs
------------------

Here is an example workflow where we are working on a spec file and testing with::

    rpkg srpm
    rpkg lint

You need to have `rpkg` installed or install it with::

    dnf install rpkg

on Fedora.

For readability we will name different SHA1 number as SHA1-A, SHA1-B. When we begin, the tree has SHA1-A::

    git commit -a -m # edit spec to comply with fedora guidelines

After the commit it now has SHA1-B::

    gitk --all

Review the changes, then do some testing. You find error,for example, rpmlint complains. Edit the spec::

    git commit -a -m # shut up rpmlint

The tree now has SHA1-C::

    rpkg srpm
    rpkg lint

We still find errors, re-edit the spec file::

    git commit -a -m # I hate you rpmlint

The tree now has SHA1-D::

    rpkg srpm
    rpkg lint

Again, still more errors, edit the spec file::

    git commit -a -m # say again something rpmlint and I kill you

The tree now has SHA1-E::

    rpkg srpm
    rpkg lint

Finally, ``rpmlint`` is silent. We will reject all our previous commits,

but they are still in git you may in following steps do in ``gitk 'Update'`` to see what happened

do not do 'Reload' as you will not see dead part of tree

::

    git reset --hard SHA1-A

We now pick up all the previous changes and apply it to our working copy without commits::

    git cherry-pick -n SHA1-B
    git cherry-pick -n SHA1-C
    git cherry-pick -n SHA1-D
    git cherry-pick -n SHA1-E

Now we have one commit including all of the changes::

    git commit -a -m # edit spec to comply with fedora guidelines

Confirm this is what we wanted and we are ready to merge and push::

    rpkg srpm
    rpkg lint
    rpkg push

Other Resources
---------------

* `Git Community Book <http://book.git-scm.com/>`_

* `The Git User's Manual <http://www.kernel.org/pub/software/scm/git/docs/user-manual.html>`_

* `Tutorial Introduction to Git <http://www.kernel.org/pub/software/scm/git/docs/gittutorial.html>`_

* `- Dealing with remote branches ..  <http://www.zorched.net/2008/04/14/start-a-new-branch-on-your-remote-git-repository/>`_

* `Git Glossary <https://git-scm.com/docs/gitglossary>`_

Credits
-------

* Originally stolen from Git guide in Spacewalk project
