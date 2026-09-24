import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string type: "pypi"
    readonly property string identifier: "pypi"
    readonly property string name: "PyPI"

    function setDict(data) {
        pypi_package_name.text = data["pypi_package_name"] || "";
        pypi_package_version.text = data["pypi_package_version"] || "";
    }

    function getDict() {
        return {
            "pypi_package_name": pypi_package_name.text,
            "pypi_package_version": pypi_package_version.text
        };
    }

    Column {
        anchors.fill: parent
        spacing: 10
        Column {
            width: parent.width
            Label {
                text: "PyPI name"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: pypi_package_name
                width: parent.width
                placeholderText: "Enter package name..."
            }
        }
        Column {
            width: parent.width
            Label {
                text: "PyPI version"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: pypi_package_version
                width: parent.width
                placeholderText: "Enter package version..."
            }
        }
    }
}
