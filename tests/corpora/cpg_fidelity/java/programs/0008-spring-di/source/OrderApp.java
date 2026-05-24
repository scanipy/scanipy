package corpus.cpg.p0008;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

/**
 * Spring-style constructor injection. The @Component / @Autowired annotations
 * are declared locally (no Spring on the classpath) so the program is
 * self-contained; they model the call edges a Spring container resolves at
 * runtime. The container-mediated wiring edge (container -> OrderService.<init>)
 * is tagged over_approximate in callgraph.json because a static front-end
 * cannot see the reflective bean instantiation.
 */
public final class OrderApp {

    @Retention(RetentionPolicy.RUNTIME)
    @interface Component {
    }

    @Retention(RetentionPolicy.RUNTIME)
    @interface Autowired {
    }

    @Component
    static final class Repository {
        String find(int id) {
            return "order#" + id;
        }
    }

    @Component
    static final class OrderService {
        private final Repository repo;

        @Autowired
        OrderService(Repository repo) {
            this.repo = repo;
        }

        String lookup(int id) {
            return repo.find(id);
        }
    }

    public static void main(String[] args) {
        Repository repo = new Repository();
        OrderService svc = new OrderService(repo);
        System.out.println(svc.lookup(7));
    }
}
