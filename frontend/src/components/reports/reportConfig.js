import definitions from './reportDefinitions.json' with { type: 'json' };
import { validateReportDefinitions } from './reportDefinitionsValidator.js';

const config = validateReportDefinitions(definitions);

export const REPORT_CATEGORIES = config.REPORT_CATEGORIES;
export const CHARTS = config.CHARTS;
export const ROLES = config.ROLES;
export const EMPTY_FORM = config.EMPTY_FORM;
export const DEFAULT_WHITE_LABEL = config.DEFAULT_WHITE_LABEL;
export const ASSISTANT_EXAMPLES = config.ASSISTANT_EXAMPLES;
export const BUSINESS_LABELS = config.BUSINESS_LABELS;
export const PERIOD_LABELS = config.PERIOD_LABELS;
export const CATEGORY_BY_KEY = Object.fromEntries(
  Object.entries(REPORT_CATEGORIES).map(([slug, category]) => [category.key, { slug, ...category }]),
);
