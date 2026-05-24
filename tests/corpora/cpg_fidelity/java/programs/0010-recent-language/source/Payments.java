package corpus.cpg.p0010;

/** JDK 17 features: record, sealed interface, instanceof pattern matching. */
public final class Payments {

    sealed interface Payment permits Card, Cash, Wire {
    }

    record Card(String number, double amount) implements Payment {
    }

    record Cash(double amount) implements Payment {
    }

    record Wire(String iban, double amount) implements Payment {
    }

    static String settle(Payment p) {
        // Uses record + sealed (finalized in Java 17) and instanceof pattern
        // matching (finalized in Java 16). Pattern-matching for switch was a
        // preview in 17 and finalized in 21, so it is deliberately avoided to
        // keep this program compilable at the declared language_level: 17.
        if (p instanceof Card c) {
            return "card:" + c.number();
        } else if (p instanceof Cash cash) {
            return "cash:" + cash.amount();
        } else if (p instanceof Wire w) {
            return "wire:" + w.iban();
        }
        throw new IllegalStateException("unreachable: sealed Payment");
    }

    public static void main(String[] args) {
        Payment p = new Card("4111", 9.99);
        System.out.println(settle(p));
    }
}
