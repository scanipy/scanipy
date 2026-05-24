package corpus.cpg.p0011;

import javax.annotation.processing.Generated;

/**
 * Simulated auto-generated source (the kind a Lombok / immutables / protobuf
 * processor emits): boilerplate getters/equals/hashCode, marked @Generated.
 * Tagged generated-code; exercises a front-end's handling of machine-emitted
 * source with repetitive structure.
 */
@Generated("com.example.codegen.DtoGenerator")
public final class UserDto {

    private final String name;
    private final int age;

    public UserDto(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() {
        return this.name;
    }

    public int getAge() {
        return this.age;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof UserDto)) {
            return false;
        }
        UserDto other = (UserDto) o;
        return this.age == other.age && this.name.equals(other.name);
    }

    @Override
    public int hashCode() {
        int result = 17;
        result = 31 * result + this.name.hashCode();
        result = 31 * result + this.age;
        return result;
    }

    public static void main(String[] args) {
        UserDto u = new UserDto("ann", 30);
        System.out.println(u.getName() + u.getAge());
    }
}
