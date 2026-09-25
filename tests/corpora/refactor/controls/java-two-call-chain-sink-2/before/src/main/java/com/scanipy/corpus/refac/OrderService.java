package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input000) throws Exception {
        String left000 = "SELECT * FROM orders WHERE id = '";
        String right000 = "'";
        String partial = left000 + input000;
        String value000 = partial + right000;
        Statement st = conn.createStatement();
        st.executeQuery(value000);
        String secondary = "archived-" + input000;
        String secondPartial = left000 + secondary;
        String secondValue = secondPartial + right000;
        st.executeQuery(secondValue);
    }
}
