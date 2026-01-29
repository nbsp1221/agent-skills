# Gitmoji Reference

Use this when the repo clearly follows gitmoji commits or explicitly requires gitmoji.

## Format

`emoji (scope): subject`

- emoji: required, from the allowed list
- scope: optional unless the repo commonly includes it
- subject: required, imperative, no period

## Allowed emoji list

Use only allowed emojis. Prefer the repo's explicit or historical emoji usage over this list when multiple options fit.
Use the repo's preferred style (emoji vs `:code:`).
If uncertain, prefer the unicode emoji (e.g., 🎨) over the shortcode (e.g., `:art:`) as it renders correctly in most git clients.

| Emoji | Code | Description | Semver |
| --- | --- | --- | --- |
| 🎨 | `:art:` | Improve structure / format of the code |  |
| ⚡️ | `:zap:` | Improve performance | Patch |
| 🔥 | `:fire:` | Remove code or files |  |
| 🐛 | `:bug:` | Fix a bug | Patch |
| 🚑️ | `:ambulance:` | Critical hotfix | Patch |
| ✨ | `:sparkles:` | Introduce new features | Minor |
| 📝 | `:memo:` | Add or update documentation |  |
| 🚀 | `:rocket:` | Deploy stuff |  |
| 💄 | `:lipstick:` | Add or update the UI and style files | Patch |
| 🎉 | `:tada:` | Begin a project |  |
| ✅ | `:white_check_mark:` | Add, update, or pass tests |  |
| 🔒️ | `:lock:` | Fix security or privacy issues | Patch |
| 🔐 | `:closed_lock_with_key:` | Add or update secrets |  |
| 🔖 | `:bookmark:` | Release / Version tags |  |
| 🚨 | `:rotating_light:` | Fix compiler / linter warnings |  |
| 🚧 | `:construction:` | Work in progress |  |
| 💚 | `:green_heart:` | Fix CI Build |  |
| ⬇️ | `:arrow_down:` | Downgrade dependencies | Patch |
| ⬆️ | `:arrow_up:` | Upgrade dependencies | Patch |
| 📌 | `:pushpin:` | Pin dependencies to specific versions | Patch |
| 👷 | `:construction_worker:` | Add or update CI build system |  |
| 📈 | `:chart_with_upwards_trend:` | Add or update analytics or track code | Patch |
| ♻️ | `:recycle:` | Refactor code |  |
| ➕ | `:heavy_plus_sign:` | Add a dependency | Patch |
| ➖ | `:heavy_minus_sign:` | Remove a dependency | Patch |
| 🔧 | `:wrench:` | Add or update configuration files | Patch |
| 🔨 | `:hammer:` | Add or update development scripts |  |
| 🌐 | `:globe_with_meridians:` | Internationalization and localization | Patch |
| ✏️ | `:pencil2:` | Fix typos | Patch |
| 💩 | `:poop:` | Write bad code that needs to be improved |  |
| ⏪️ | `:rewind:` | Revert changes | Patch |
| 🔀 | `:twisted_rightwards_arrows:` | Merge branches |  |
| 📦️ | `:package:` | Add or update compiled files or packages | Patch |
| 👽️ | `:alien:` | Update code due to external API changes | Patch |
| 🚚 | `:truck:` | Move or rename resources (e.g.: files, paths, routes) |  |
| 📄 | `:page_facing_up:` | Add or update license |  |
| 💥 | `:boom:` | Introduce breaking changes | Major |
| 🍱 | `:bento:` | Add or update assets | Patch |
| ♿️ | `:wheelchair:` | Improve accessibility | Patch |
| 💡 | `:bulb:` | Add or update comments in source code |  |
| 🍻 | `:beers:` | Write code drunkenly |  |
| 💬 | `:speech_balloon:` | Add or update text and literals | Patch |
| 🗃️ | `:card_file_box:` | Perform database related changes | Patch |
| 🔊 | `:loud_sound:` | Add or update logs |  |
| 🔇 | `:mute:` | Remove logs |  |
| 👥 | `:busts_in_silhouette:` | Add or update contributor(s) |  |
| 🚸 | `:children_crossing:` | Improve user experience / usability | Patch |
| 🏗️ | `:building_construction:` | Make architectural changes |  |
| 📱 | `:iphone:` | Work on responsive design | Patch |
| 🤡 | `:clown_face:` | Mock things |  |
| 🥚 | `:egg:` | Add or update an easter egg | Patch |
| 🙈 | `:see_no_evil:` | Add or update a .gitignore file |  |
| 📸 | `:camera_flash:` | Add or update snapshots |  |
| ⚗️ | `:alembic:` | Perform experiments | Patch |
| 🔍️ | `:mag:` | Improve SEO | Patch |
| 🏷️ | `:label:` | Add or update types | Patch |
| 🌱 | `:seedling:` | Add or update seed files |  |
| 🚩 | `:triangular_flag_on_post:` | Add, update, or remove feature flags | Patch |
| 🥅 | `:goal_net:` | Catch errors | Patch |
| 💫 | `:dizzy:` | Add or update animations and transitions | Patch |
| 🗑️ | `:wastebasket:` | Deprecate code that needs to be cleaned up | Patch |
| 🛂 | `:passport_control:` | Work on code related to authorization, roles and permissions | Patch |
| 🩹 | `:adhesive_bandage:` | Simple fix for a non-critical issue | Patch |
| 🧐 | `:monocle_face:` | Data exploration/inspection |  |
| ⚰️ | `:coffin:` | Remove dead code |  |
| 🧪 | `:test_tube:` | Add a failing test |  |
| 👔 | `:necktie:` | Add or update business logic | Patch |
| 🩺 | `:stethoscope:` | Add or update healthcheck |  |
| 🧱 | `:bricks:` | Infrastructure related changes |  |
| 🧑‍💻 | `:technologist:` | Improve developer experience |  |
| 💸 | `:money_with_wings:` | Add sponsorships or money related infrastructure |  |
| 🧵 | `:thread:` | Add or update code related to multithreading or concurrency |  |
| 🦺 | `:safety_vest:` | Add or update code related to validation |  |
| ✈️ | `:airplane:` | Improve offline support |  |
| 🦖 | `:t-rex:` | Code that adds backwards compatibility |  |

## Subject rules

- Imperative: `add`, `fix`, `update`, `remove`
- Start subject with a capital letter
- Try <= 50 chars; hard limit 72 unless the repo allows longer
- No trailing period

## Scope rules

- Use kebab-case: `auth-flow`, `api-client`
- Only use scopes that appear in repo history or docs

## Body and trailers

- Use a body for non-trivial changes; wrap at 72 chars
- Use trailers when relevant: `Fixes #123`, `Refs #123`

## Breaking changes

Use only for backward-incompatible changes that break users or public interfaces (API, CLI, config, data behavior). Do not use for internal refactors.

Use one of:
- `💥 (scope): subject`
- `:boom: (scope): subject`

## Reverts

Use `⏪` (`:rewind:`) type and explain the revert in the body if possible.

## Examples

### Good

- `🎨 Improve header layout`
- `♻️ (components): Refactor button hooks`
- `:bug: Fix login crash`

### Bad

- `🎨 Improve header layout.` (period)
- `🐛 Fixed login crash` (past tense)
- `♻️ refactor button hooks` (lowercase start)
- `🦄 Add payment gateway` (unknown emoji)
