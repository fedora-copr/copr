# Copyright 2008, Steve 'Ashcrow' Milner <smilner@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

BUILD_DIR := build

# Python doc related
EPYDOC_BIN := `which epydoc`
EPYDOC_SWITCHES := --inheritance listed --graph all --html
PYTHON_DOC_DIR := python-doc
PYTHON_DIRS := ../coprs_frontend 

# TARGETS
# schema is not incldued here, since you need a live db
all: python

python:
	mkdir -p $(BUILD_DIR)/py-doc-build
	$(SHELL ulimit -n 4096)
	echo "[epydoc]" > $(BUILD_DIR)/epydoc.lst
	echo -n "modules: " >> $(BUILD_DIR)/epydoc.lst
	find $(PYTHON_DIRS) -type f -name '*.py' | grep -v test | xargs echo -n >> $(BUILD_DIR)/epydoc.lst
	$(EPYDOC_BIN) $(EPYDOC_SWITCHES) -o $(PYTHON_DOC_DIR) --config $(BUILD_DIR)/epydoc.lst

clean:
	rm -rf build/

distclean:
	rm -rf build/ $(PYTHON_DOC_DIR) $(JAVA_DOC_DIR) $(SCHEMA_DOC_DIR)
