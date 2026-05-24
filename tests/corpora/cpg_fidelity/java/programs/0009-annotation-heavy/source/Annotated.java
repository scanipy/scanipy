package corpus.cpg.p0009;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/** Annotation-heavy program: parse cost dominated by annotation declarations. */
public final class Annotated {

    @Documented
    @Retention(RetentionPolicy.RUNTIME)
    @Target({ElementType.METHOD, ElementType.TYPE})
    @interface Audited {
        String value() default "";

        int level() default 1;
    }

    @Documented
    @Retention(RetentionPolicy.RUNTIME)
    @Target(ElementType.PARAMETER)
    @interface NonNull {
    }

    @Audited(value = "service", level = 3)
    static final class Service {

        @Audited("compute")
        int compute(@NonNull String key) {
            return key.length();
        }
    }

    public static void main(String[] args) {
        Service s = new Service();
        System.out.println(s.compute("hello"));
    }
}
