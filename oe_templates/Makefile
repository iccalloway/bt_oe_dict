#
# Makefile
#
#
#

###########################

# You need to edit these values.

DICT_NAME		=	"An Anglo-Saxon Dictionary"
DICT_SRC_PATH		=	MyDictionary.xml
CSS_PATH		=	MyDictionary.css
PLIST_PATH		=	MyInfo.plist

DICT_BUILD_OPTS		=
# Suppress adding supplementary key.
# DICT_BUILD_OPTS		=	-s 0	# Suppress adding supplementary key.

###########################

# The DICT_BUILD_TOOL_DIR value is used also in "build_dict.sh" script.
# You need to set it when you invoke the script directly.

DICT_BUILD_TOOL_DIR	=	"/Users/work/Documents/Git/Dictionary-Development-Kit"
#DICT_BUILD_TOOL_DIR	=	"/Developer/Extras/Dictionary Development Kit"
DICT_BUILD_TOOL_BIN	=	"$(DICT_BUILD_TOOL_DIR)/bin"

###########################

DICT_DEV_KIT_OBJ_DIR	=	./objects
export	DICT_DEV_KIT_OBJ_DIR

DESTINATION_FOLDER	=	~/Library/Dictionaries
RM			=	/bin/rm

###########################

all:
	"$(DICT_BUILD_TOOL_BIN)/build_dict.sh" $(DICT_BUILD_OPTS) $(DICT_NAME) $(DICT_SRC_PATH) $(CSS_PATH) $(PLIST_PATH)
	echo "Done."


install:
	echo "Installing into $(DESTINATION_FOLDER)".
	-killall Dictionary 2>/dev/null || true
	-killall DictionaryServiceHelper 2>/dev/null || true
	mkdir -p $(DESTINATION_FOLDER)
	$(RM) -rf $(DESTINATION_FOLDER)/$(DICT_NAME).dictionary
	ditto --noextattr --norsrc $(DICT_DEV_KIT_OBJ_DIR)/$(DICT_NAME).dictionary  $(DESTINATION_FOLDER)/$(DICT_NAME).dictionary
	/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $$(date +%Y.%m.%d.%H%M%S)" $(DESTINATION_FOLDER)/$(DICT_NAME).dictionary/Contents/Info.plist
	touch $(DESTINATION_FOLDER)
	echo "Done."
	echo "To test the new dictionary, open Dictionary.app."

clean:
	$(RM) -rf $(DICT_DEV_KIT_OBJ_DIR)
