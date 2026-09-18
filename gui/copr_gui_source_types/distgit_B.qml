import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string identifier: "distgit-B"
    readonly property string name: "DistGit"
    
    function setName(name) {
        packagename.text = name;
    }

    function setDict(data) {
        committish.text = data["committish"] || "";
        namespace.text = data["namespace"] || "";
        distgit.text = data["distgit"] || "";
    }

    function isempty(str) {
        return typeof str === "string" && str.length === 0;
    }

    function getDict() {
        var ret = {
            "packagename": packagename.text
        };
        var com = committish.text;
        var nmsp = namespace.text;
        var dgit = distgit.text;
        if (!isempty(com)) {
            ret["committish"] = com;
        }
        if (!isempty(nmsp)) {
            ret["namespace"] = nmsp;
        }
        if (!isempty(dgit)) {
            ret["distgit"] = dgit;
        }
        return ret;
    }

    Column {
        anchors.fill: parent
        spacing: 10
        Column {
            width: parent.width
            Label {
                text: "Package name"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }
            TextField {
                id: packagename
                width: parent.width
                placeholderText: "Enter package name..."
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
                text: "Namespace"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: namespace
                width: parent.width
                placeholderText: "Enter namespace..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "Distgit"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: distgit
                width: parent.width
                placeholderText: "Enter distgit..."
            }
        }
    }
}
