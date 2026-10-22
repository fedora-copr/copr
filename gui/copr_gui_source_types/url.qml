import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string type: "url"
    readonly property string identifier: "url-B"
    readonly property string name: "Url"

    function setDict(data) {
        url.text = data["url"];
    }

    function getDict() {
        return {
            "url": url.text
        };
    }

    Column {
        anchors.fill: parent
        spacing: 10
        Column {
            width: parent.width
            Label {
                text: "URL"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: url
                width: parent.width
                placeholderText: "Enter URL..."
            }
        }
    }
}
