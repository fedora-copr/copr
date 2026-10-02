import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string type: "custom"
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
        return typeof str === "string" && str.length === 0
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

        if (!isempty(resultdir)) {
            ret["resultdir"] = resultdir
        }

        if (!isempty(builddeps)) {
            ret["builddeps"] = builddeps
        }

        if (!isempty(repos)) {
            ret["repos"] = repos
        }

        return ret
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 1

        // -------------------------------------------------
        // Script
        // -------------------------------------------------

        Label {
            text: "Script"

            // qmllint disable unqualified
            color: textColor
            // qmllint enable unqualified
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 100

            TextArea {
                id: script_text

                width: parent.width

                textFormat: TextEdit.PlainText
                placeholderText: "Enter script..."
                wrapMode: TextEdit.NoWrap
            }
        }

        // -------------------------------------------------
        // Chroot
        // -------------------------------------------------

        Label {
            text: "Chroot"

            // qmllint disable unqualified
            color: textColor
            // qmllint enable unqualified
        }

        TextField {
            id: script_chroot

            Layout.fillWidth: true

            placeholderText: "Enter chroot..."
        }

        // -------------------------------------------------
        // Resultdir
        // -------------------------------------------------

        Label {
            text: "Resultdir"

            // qmllint disable unqualified
            color: textColor
            // qmllint enable unqualified
        }

        TextField {
            id: script_resultdir

            Layout.fillWidth: true

            placeholderText: "Enter resultdir..."
        }

        // -------------------------------------------------
        // Builddeps
        // -------------------------------------------------

        Label {
            text: "Builddeps"

            // qmllint disable unqualified
            color: textColor
            // qmllint enable unqualified
        }

        TextField {
            id: script_builddeps

            Layout.fillWidth: true

            placeholderText: "Enter builddeps..."
        }

        // -------------------------------------------------
        // Repos
        // -------------------------------------------------

        Label {
            text: "Repos"

            // qmllint disable unqualified
            color: textColor
            // qmllint enable unqualified
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            Layout.minimumHeight: 80

            TextArea {
                id: script_repos

                width: parent.width

                textFormat: TextEdit.PlainText
                placeholderText: "Enter repos..."
                wrapMode: TextEdit.NoWrap
            }
        }
    }
}
