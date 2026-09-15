// ESLint flat config. Added on post-coding Day 3 (stage 12).
//
// Until Day 3 the project had no linter configuration, which meant "the frontend
// lints clean" was not a statement anyone else could check. Run it with:
//
//     npm run lint
//
// Rule choice is deliberately the *correctness* half of ESLint, not style:
// prettier owns formatting (see .prettierrc), so enabling stylistic rules here
// would only produce findings that duplicate the formatter and bury real ones.
import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}', '*.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: '18.3' } },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // Vite's automatic JSX runtime means React is never imported explicitly,
      // so these two legacy rules would otherwise fire on every file.
      'react/react-in-jsx-scope': 'off',
      // No TypeScript and no prop-types in this project; the component contracts
      // are documented in each component's header comment instead.
      'react/prop-types': 'off',
    },
  },
]
