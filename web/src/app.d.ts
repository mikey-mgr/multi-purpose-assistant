import type { Session, User } from 'better-auth';

declare global {
	namespace App {
		interface Platform {
			env: Env;
			ctx: ExecutionContext;
			caches: CacheStorage;
			cf?: IncomingRequestCfProperties;
		}

		interface Locals {
			user: User | null;
			session: Session | null;
		}
	}
}

export {};
