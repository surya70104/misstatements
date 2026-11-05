import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['node_modules', 'dist', '.vite'] },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
      globals: { ...globals.browser },
    },
  },
  {
    // Tests hand `vi.fn` spies to `expect`; they never rely on `this`.
    files: ['tests/**'],
    rules: { '@typescript-eslint/unbound-method': 'off' },
  },
)
