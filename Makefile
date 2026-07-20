SKILLS_SRC := .agents/skills
SKILLS_DST := .bob/skills

.PHONY: install-skills help

## install-skills: Copy all agent skills into .bob/skills so Bob picks them up
install-skills:
	@echo "Installing skills from $(SKILLS_SRC) → $(SKILLS_DST)"
	@mkdir -p $(SKILLS_DST)
	@for skill_dir in $(SKILLS_SRC)/*/; do \
		skill_name=$$(basename "$$skill_dir"); \
		dest=$(SKILLS_DST)/$$skill_name; \
		mkdir -p "$$dest"; \
		cp -f "$$skill_dir/SKILL.md" "$$dest/SKILL.md"; \
		echo "  ✔ $$skill_name"; \
	done
	@echo "Done. $(shell ls $(SKILLS_SRC) | wc -l | tr -d ' ') skill(s) installed."

## help: Show available targets
help:
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  /'
