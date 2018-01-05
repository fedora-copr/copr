# blog-tutorial-layered2

Hello, this is an example repository to demonstrate COPR SCM abilities. To understand
the following description better, please see [blog-tutorial-flat-packed](https://github.com/clime/blog-tutorial-flat-packed) and [blog-tutorial-flat-unpacked](https://github.com/clime/blog-tutorial-flat-unpacked) first.

Content of this repository is layered. 

**Layered** means there are some non-root subpackages in the repository. In other words,
there are some subdirectories that contain a spec file. 

- Subpackage `subpkg1` is packed.
- Subpackage `subpkg2` is unpacked.

Now note that so far we have assumed that subpackage is a subdirectory that contains a spec file and that spec file
will be used for SRPM generation (building SRPM precedes building RPM in COPR). **_But_** that might not always be the case.

What you can actually do is to use the content of `subpkg1` together with the spec file `your.spec` placed in `rpm` subdirectory and build the SRPM out of those two. If you know `rpmbuild` tool, this basically translates to calling 
`rpmbuild -bs rpm/your.spec --define '%_sourcedir subpkg1'`. You can do the same thing for `subpkg2` and `rpm/your.spec` by the way.

If you use `rpm/your.spec`, then the `subpkg1/my.spec` is just a normal file and it is not even required for it to be present in the `subpkg1` subdirectory. That basically means you can make a subpackage out of any subdirectory in your repository whether it
contains a spec file or not if you additionaly say what spec file should be used for SRPM generation.

Knowing that **subpackage** is really formed by any `spec file` together with some `source directory` makes formal defintions of **flat** and **layered** more complicated. Let's just say that [blog-tutorial-flat-unpacked](https://github.com/clime/blog-tutorial-flat-unpacked) repository is called **flat** because `source directory` for its only subpackage is a root directory and this repository is **layered** because it contains at least one subpackage of which its `source directory` is not a root directory.
Note that there can be no subpackages in a repository if that repository does not contain a spec file.

What is probably even more curious is the true difference between **packed** and **unpacked** subpackages. Previously, we have said that:

**Packed** means the application source files are packed into a tarball being referenced by a Source directive in the .spec file.

and

**Unpacked** means the application source files are not packed into a tarball that would be referenced by a Source directive in the spec file.

This is basically correct, although still rather an intuitive explanation. What it does not really say, for example, is: 
- what exactly is considered to be an *application source file*
- what happens if there are no *application source files* in the repository but also no files (tarballs) referenced from the spec file by a Source directive

To asnwer these questions we need to be precise about what those terms mean:

        "packed": does not contain anything else
                  except ignored files or contains
                  at least one source referenced
                  by the given specfile
                  
and

        "unpacked": is not "packed", meaning that
                    it contains at least one non-ignored
                    file and contains no file referenced
                    by the given specfile as a source
                    
Note that:

        "source": is a filename specified in a Source 
                  or Patch .spec directive
        
and that ignored files are described by the following (case-insensitive) regular expression:

        ignore_file_regex = '(^README|.spec$|^\.|^tito.props$|^sources$)'

Now, these definitions (wired into https://pagure.io/rpkg-client) are really mind-boggling 
and I would recommend to just stick to the previous intutitive ones but what they allow, in the end,
is that you can use the rpkg-client tool to call `rpkg srpm` for a given subpackage and it will do the right thing:

- For a packed subpackage composed of `subpkg1.spec` spec file and `subpkg1_sourcedir`source directory, it will basically just invoke:

      rpmbuild -bs subpkg1.spec --define '%_sourcedir subpkg1_sourcedir'

which is what person familiar with `rpmbuild` would expect.

- For an unpacked subpackage composed of `subpkg2.spec` spec file and `subpkg2_sourcedir`source directory, it will do little bit of preprocessing first, packing the content of `subpkg2_sourcedir` into a tarball named according to `Source0` definition in the provided `subpkg2.spec` and placing it into the `subpkg2_sourcedir` before invoking the same `rpmbuild` command as before for the packed subpackage. That is:

      rpmbuild -bs subpkg2.spec --define '%_sourcedir subpkg2_sourcedir'
 
This is the magic that really makes the SCM method in COPR so versatile that it can handle both types of subpackages without asking a user about the content type.

Now let's finally answer the unanswered questions that we were interested in:

- what exactly is considered to be an *application source file*
  - a non-ignored file
  
- what happens if there are no *application source files* in the repository but also no files (tarballs) referenced from the spec file by a Source directive
  - not that much but the repository contains a subpackage of **packed** type 

update
