import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string identifier: "rubygems"
    readonly property string name: "RubyGems"

    function setDict(data) {
        gem_name.text = data["gem_name"] || "";
    }

    function getDict() {
        return {
            "gem_name": gem_name.text
        };
    }

    Column {
        anchors.fill: parent
        spacing: 10
        Column {
            width: parent.width
            Label {
                text: "Rubygem"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: gem_name
                width: parent.width
                placeholderText: "Enter Rubygem..."
            }
        }
    }
}
