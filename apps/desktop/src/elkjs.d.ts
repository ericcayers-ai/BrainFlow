declare module "elkjs/lib/elk.bundled.js" {
  export default class ELK {
    layout(graph: unknown): Promise<{
      children?: Array<{
        id: string;
        x?: number;
        y?: number;
        width?: number;
        height?: number;
      }>;
    }>;
    terminateWorker?(): void;
  }
}

declare module "ajv/dist/2020.js" {
  import type { ErrorObject } from "ajv";
  export default class Ajv2020 {
    constructor(opts?: object);
    compile(
      schema: object,
    ): ((data: unknown) => boolean) & { errors?: ErrorObject[] | null };
  }
}
