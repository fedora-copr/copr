import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string identifier: "custom"
    readonly property string name: "Custom Script"

    function setDict(data) {
        script_text.text = data["script"]
        script_chroot.text = data["chroot"]
        script_resultdir.text = data["resultdir"]
        script_builddeps.text = data["builddeps"]
        script_repos.text = data["repos"]
    }

    function isempty(str) {
        return typeof str === "string" && str.length === 0;
    }
    
    function getDict() {
        var ret = {
            "script": script_text.text
        }
        var chroot = script_chroot.text
        var resultdir = script_resultdir.text
        var builddeps = script_builddeps.text
        var repos = script_repos.text
        if (isempty(chroot)) {
            chroot = "fedora-latest-x86_64"
        }
        ret["chroot"] = chroot
        if (isempty(resultdir)) {
            ret["resultdir"] = resultdir
        }
        if (isempty(builddeps)) {
            ret["builddeps"] = builddeps
        }
        if (isempty(repos)) {
            ret["repos"] = repos
        }
        return ret
    }

    Column {
        spacing: 10
        anchors.fill: parent

        Column {
            width: parent.width
            Label {
                text: "Script"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextArea {
                id: script_text
                textFormat: TextEdit.PlainText
                placeholderText: "Enter script..."
            }
        }

        Column {
            width: parent.width
            Label {
                text: "Chroot"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: script_chroot
                width: parent.width
                placeholderText: "Enter chroot..."
            }
        }

        Column {
            width: parent.width
            Label {
                text: "Resultdir"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: script_resultdir
                width: parent.width
                placeholderText: "Enter resultdir..."
            }
        }

        Column {
            width: parent.width
            Label {
                text: "Builddeps"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: script_builddeps
                width: parent.width
                placeholderText: "Enter builddeps..."
            }
        }

        Column {
            width: parent.width
            Label {
                text: "Repos"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextArea {
                id: script_repos
                textFormat: TextEdit.PlainText
                placeholderText: "Enter repos..."
            }
        }
    }
}
