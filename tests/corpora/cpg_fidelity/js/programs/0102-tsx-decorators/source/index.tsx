// CMP-CORP-CPG-js synthesized program 0102
// Coverage: jsx-tsx, decorators-experimental (TS surface, parse-success stressor)
function sealed(constructor: Function): void {
  Object.seal(constructor);
  Object.seal(constructor.prototype);
}

@sealed
export class Greeter {
  constructor(private readonly name: string) {}

  greeting(): string {
    return `Hello, ${this.name}`;
  }
}

function renderName(name: string): string {
  const g = new Greeter(name);
  return g.greeting();
}

export function App(props: { name: string }): JSX.Element {
  const text = renderName(props.name);
  return <div className="greeter">{text}</div>;
}
