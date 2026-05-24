// SYNTHESIZED Juliet-shaped CWE-89 case (Public Domain, authored for CMP-CORP-VULN-01).
// Ground truth: tainted source (System.getenv) reaches the executeQuery sink (line 18).
public class SqliConnectExecuteQuery01 {
    public void action(java.sql.Connection conn) throws java.sql.SQLException {
        String data = System.getenv("ADD"); // BadSource: untrusted environment value
        if (data != null) {
            String query = "SELECT * FROM users WHERE name = '" + data + "'";
            java.sql.Statement statement = conn.createStatement();
            java.sql.ResultSet rs = statement.executeQuery(query); // SINK (CWE-89)
            rs.close();
        }
    }
}
