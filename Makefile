# Internal goals

all:
	python3 parsemacs.py /usr/share/emacs/23.4
	python3 parsemacs.py ~/emacs/_/gnus/lisp
	python3 parsemacs.py ~/emacs/_/org-mode/lisp

