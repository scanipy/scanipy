// CMP-CORP-CPG-js synthesized program 0101
// Coverage: module-system-esm, type-informed-dispatch (TS surface)
export interface Shape {
  area(): number;
}

export class Circle implements Shape {
  constructor(private readonly r: number) {}
  area(): number {
    return Math.PI * this.r * this.r;
  }
}

export class Square implements Shape {
  constructor(private readonly side: number) {}
  area(): number {
    return this.side * this.side;
  }
}

export function totalArea(shapes: Shape[]): number {
  let sum = 0;
  for (const s of shapes) {
    // type-informed dispatch: target set {Circle.area, Square.area} via tsc
    sum += s.area();
  }
  return sum;
}

export function makeShapes(): Shape[] {
  return [new Circle(2), new Square(3)];
}
