package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input008) throws Exception {
        String left008 = "SELECT * FROM orders WHERE id = '";
        String right008 = "'";
        String value008 = _extracted_value(left008, input008, right008);
        Statement st = conn.createStatement();
        st.executeQuery(value008);
    }

    private static String _extracted_value(String left008, String input008, String right008) {
        return left008 + input008 + right008;
    }
}
