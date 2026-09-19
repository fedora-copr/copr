import QtQuick
import QtQuick.Controls


Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string type: "scm"
    readonly property string identifier: "scm"
    readonly property string name: "Source Control Manager"

    function setDict(data) {
        clone_url.text = data.clone_url;
        committish.text = data.committish;
        subdirectory.text = data.subdirectory;
        specfile.text = data.spec;
        
        var scm_type_str = data.type
        if (! scm_type_str){
            scm_type_str = data.scm_type
        }

        if (scm_type_str) {
            var scmIndex = scm_type.find(scm_type_str);
            if (scmIndex !== -1) {
                scm_type.currentIndex = scmIndex;
            }
        }

        if (data.source_build_method) {
            var buildIndex = method.find(data.source_build_method);
            if (buildIndex !== -1) {
                method.currentIndex = buildIndex;
            }
        }
    }
    
    function getDict() {
        var cloneurl = clone_url.text;
        var ref = committish.text;
        var subdir = subdirectory.text;
        var spec = specfile.text;
        var type = scm_type.currentText;
        var build = method.currentText;
        return {
                "clone_url": cloneurl,
                "committish": ref,
                "subdirectory": subdir,
                "spec": spec,
                "scm_type": type,
                "source_build_method": build
        };
    }

    Column {
        anchors.fill: parent
        spacing: 10
        Column {
            width: parent.width
            Label {
                text: "Clone URL"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: clone_url
                width: parent.width
                placeholderText: "Enter clone url..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "Committish"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: committish
                width: parent.width
                placeholderText: "Enter name of a branch, tag, or a git hash..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "Subdirectory"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: subdirectory
                width: parent.width
                placeholderText: "Enter subdirectory..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "Spec file"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: specfile
                width: parent.width
                placeholderText: "Enter specfile path..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "SCM Type"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            ComboBox {
                id: scm_type
                width: parent.width
                editable: false
                model: ["git", "svn"]
                currentIndex: 0
            }
        }
        Column {
            width: parent.width
            Label {
                text: "Build method"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            ComboBox {
                id: method
                width: parent.width
                editable: false
                model: ["rpkg", "tito", "tito_test", "make_srpm"]
                currentIndex: 0
            }
        }
    }
}
