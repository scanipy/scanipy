package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input016) throws Exception {
        String left016 = "SELECT * FROM orders WHERE id = '";
        String right016 = "'";
        String value016 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value016);
        st.setString(1, input016);
        st.executeQuery();
    }
}
