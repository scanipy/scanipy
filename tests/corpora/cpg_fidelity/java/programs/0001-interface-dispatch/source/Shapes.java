package corpus.cpg.p0001;

/** Polymorphic dispatch through an interface declaration. */
public final class Shapes {

    interface Shape {
        double area();
    }

    static final class Circle implements Shape {
        private final double r;

        Circle(double r) {
            this.r = r;
        }

        @Override
        public double area() {
            return Math.PI * r * r;
        }
    }

    static final class Square implements Shape {
        private final double s;

        Square(double s) {
            this.s = s;
        }

        @Override
        public double area() {
            return s * s;
        }
    }

    static double total(Shape a, Shape b) {
        return a.area() + b.area();
    }

    public static void main(String[] args) {
        Shape c = new Circle(2.0);
        Shape s = new Square(3.0);
        System.out.println(total(c, s));
    }
}
