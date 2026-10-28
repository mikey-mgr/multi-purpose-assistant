export type RuntimeEnv = Record<string, string | undefined>;

let current: RuntimeEnv = {};

export function setRuntimeEnv(env: RuntimeEnv | undefined) {
	if (env) current = env;
}

export function envValue(name: string): string | undefined {
	if (current[name] !== undefined) return current[name];
	if (typeof process !== 'undefined') return process.env[name];
	return undefined;
}
