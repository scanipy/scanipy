package corpus.cpg.p0007;

/** CFG correctness through try-with-resources + Throwable.addSuppressed. */
public final class Resources {

    static final class Handle implements AutoCloseable {
        private final String name;

        Handle(String name) {
            this.name = name;
        }

        String read() {
            return "data:" + name;
        }

        @Override
        public void close() {
            // released
        }
    }

    static String load(String name) {
        try (Handle h = new Handle(name)) {
            return h.read();
        }
    }

    public static void main(String[] args) {
        System.out.println(load("file"));
    }
}
