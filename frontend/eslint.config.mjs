import nextConfig from "eslint-config-next";
import prettierConfig from "eslint-config-prettier";

const eslintConfig = [
  ...nextConfig,
  prettierConfig,
  {
    rules: {
      // Acessibilidade — erros duros (jsx-a11y já vem do next config)
      "jsx-a11y/alt-text": "error",
      "jsx-a11y/aria-props": "error",
      "jsx-a11y/aria-role": "error",
      "jsx-a11y/aria-unsupported-elements": "error",
      "jsx-a11y/role-has-required-aria-props": "error",
      "jsx-a11y/role-supports-aria-props": "error",
    },
  },
];

// Find the TS config from next and extend its rules
const tsConfigIndex = eslintConfig.findIndex(
  (c) => c.plugins && c.plugins["@typescript-eslint"],
);
if (tsConfigIndex !== -1) {
  eslintConfig[tsConfigIndex] = {
    ...eslintConfig[tsConfigIndex],
    rules: {
      ...eslintConfig[tsConfigIndex].rules,
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  };
}

export default eslintConfig;
