package corpus.cpg.p0002;

/** Virtual dispatch over a class hierarchy with overrides. */
public final class Animals {

    abstract static class Animal {
        abstract String speak();

        String describe() {
            return "I say " + speak();
        }
    }

    static class Dog extends Animal {
        @Override
        String speak() {
            return "woof";
        }
    }

    static class Puppy extends Dog {
        @Override
        String speak() {
            return "yip";
        }
    }

    static String greet(Animal a) {
        return a.describe();
    }

    public static void main(String[] args) {
        Animal a = new Puppy();
        System.out.println(greet(a));
    }
}
