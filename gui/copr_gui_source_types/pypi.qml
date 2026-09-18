import QtQuick
import QtQuick.Controls

Rectangle {
    // qmllint disable unqualified
    color: windowColor
    // qmllint enable unqualified

    readonly property string identifier: "pypi"
    readonly property string name: "PyPI"

    function isempty(str) {
        return typeof str === "string" && str.length === 0;
    }

    function setDict(data) {
        pypi_package_name.text = data["package_name"] || "";
        pypi_package_version.text = data["version"] || "";

        var generatorIndex = spec_generator.find(data["spec_generator"]);
        if (generatorIndex !== -1) {
            spec_generator.currentIndex = generatorIndex;
        }

        spec_template.text = data["template"] || "";

        var versions = data["python_versions"]
        if (versions) {
            var has2 = versions.indexOf("2") !== -1;
            var has3 = versions.indexOf("3") !== -1;

            if (has2) {
                if (has3){
                    python_versions.currentIndex = 2;
                } else {
                    python_versions.currentIndex = 1;
                } 
            } else {
                python_versions.currentIndex = 0;
            }
        }
    }

    function getDict() {
        var ret = {
            "pypi_package_name": pypi_package_name.text
        };

        if (!isempty(pypi_package_version.text)) {
            ret["pypi_package_version"] = pypi_package_version.text;
        }

        ret["spec_generator"] = spec_generator.currentText;

        if (spec_generator.currentText === "pyp2rpm") {
            if (!isempty(spec_template.text)) {
                ret["spec_template"] = spec_template.text;
            }

            ret["python_versions"] = python_versions.currentText.split(",");
        }

        return ret;
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
        Column {
            width: parent.width
            Label {
                text: "PyPI spec generator"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            ComboBox {
                id: spec_generator
                width: parent.width
                editable: false
                model: ["pyp2spec", "pyp2rpm"]
                currentIndex: 0
            }
        }
        Column {
            visible: spec_generator.currentIndex !== 0
            width: parent.width
            Label {
                text: "pyp2rpm template"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            TextField {
                id: spec_template
                width: parent.width
                placeholderText: "Enter template..."
            }
        }
        Column {
            visible: spec_generator.currentIndex !== 0
            width: parent.width
            Label {
                text: "python versions"
                // qmllint disable unqualified
                color: textColor
                // qmllint enable unqualified
            }

            ComboBox {
                id: python_versions
                width: parent.width
                editable: false
                model: ["3", "2", "3,2"]
                currentIndex: 0
            }
        }
    }
}
